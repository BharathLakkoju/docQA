"""Phase 1c — pull real .github/workflows/*.yml files via the GitHub REST
Search Code API, using the local `gh` CLI's own auth (never touches the
token directly — every call is a `gh api` subprocess so the token never
appears in this process's stdout/logs).

Per CLAUDE.md's licensing rule: most raw GitHub workflow files carry no
explicit license (all-rights-reserved by default), so this pull is used for
retrieval-at-inference (building the local Pinecone index) only. Raw YAML
lands in data/raw/ which is gitignored — it is not committed/redistributed
as a bundled dataset. (The Cardoen/Mens/Decan Zenodo dataset is the
explicitly-licensed alternative named in INSTRUCTIONS.md 1c for anything
that *would* need to be redistributed; its raw archive is 1.4GB, worked
out as an unnecessary download for a locally-built index.)

Respects the Search Code API's 30 req/min budget on this token (checked via
`gh api rate_limit`) with a conservative pacing.

Output:
  data/raw/github_actions/live/{sha}.yml
  data/processed/github_actions/workflow_attributions.csv
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

from tqdm import tqdm

# Varied qualifiers to diversify the sample beyond whatever the default
# relevance ranking would return for a single generic query.
SEARCH_QUERIES = [
    '"actions/checkout" path:.github/workflows extension:yml',
    "matrix strategy path:.github/workflows extension:yml",
    "docker build push path:.github/workflows extension:yml",
    "pull_request path:.github/workflows extension:yml",
    "workflow_dispatch path:.github/workflows extension:yml",
    '"actions/setup-node" path:.github/workflows extension:yml',
    '"actions/setup-python" path:.github/workflows extension:yml',
    "pytest path:.github/workflows extension:yml",
    "npm test path:.github/workflows extension:yml",
    "deploy production path:.github/workflows extension:yml",
    "release please path:.github/workflows extension:yml",
    "terraform apply path:.github/workflows extension:yml",
    "golangci-lint path:.github/workflows extension:yml",
    '"actions/cache" path:.github/workflows extension:yml',
    "self-hosted runner path:.github/workflows extension:yml",
]


def gh_api(endpoint: str, params: list[str] | None = None) -> dict:
    cmd = ["gh", "api", "-X", "GET", endpoint]
    for p in params or []:
        cmd += ["-f", p]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:300])
    return json.loads(result.stdout)


def search_page(query: str, page: int) -> dict:
    return gh_api("search/code", [f"q={query}", "per_page=50", f"page={page}"])


def fetch_content(contents_url_path: str) -> dict:
    return gh_api(contents_url_path)


def fetch_license(full_name: str, cache: dict) -> str:
    if full_name in cache:
        return cache[full_name]
    try:
        repo = gh_api(f"repos/{full_name}")
        license_id = (repo.get("license") or {}).get("spdx_id") or "NOASSERTION"
    except RuntimeError:
        license_id = "unknown"
    cache[full_name] = license_id
    return license_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=300, help="max unique-content files to pull")
    parser.add_argument("--pages-per-query", type=int, default=2)
    parser.add_argument("--out-dir", default="data/raw/github_actions/live")
    parser.add_argument("--attributions-csv", default="data/processed/github_actions/workflow_attributions.csv")
    parser.add_argument("--pace-seconds", type=float, default=2.1, help="delay between search requests (30/min budget)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attr_path = Path(args.attributions_csv)
    attr_path.parent.mkdir(parents=True, exist_ok=True)

    seen_shas: dict[str, dict] = {}
    for query in tqdm(SEARCH_QUERIES, desc="search queries"):
        if len(seen_shas) >= args.limit:
            break
        for page in range(1, args.pages_per_query + 1):
            try:
                data = search_page(query, page)
            except RuntimeError as e:
                print(f"  [skip] {query!r} page {page}: {e}", file=sys.stderr)
                break
            time.sleep(args.pace_seconds)
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                sha = item.get("sha")
                if sha and sha not in seen_shas:
                    seen_shas[sha] = item
            if len(seen_shas) >= args.limit:
                break

    candidates = list(seen_shas.values())[: args.limit]
    print(f"Collected {len(candidates)} unique-content candidate files. Fetching content + repo license ...")

    license_cache: dict[str, str] = {}
    attr_rows = []
    fetched = 0
    today = time.strftime("%Y-%m-%d")

    for item in tqdm(candidates, desc="fetching content"):
        sha = item["sha"]
        dest = out_dir / f"{sha}.yml"
        repo = item["repository"]["full_name"]
        path = item["path"]
        html_url = item["html_url"]

        if not dest.exists():
            try:
                content_url_path = item["url"].split("api.github.com/")[-1]
                content_data = fetch_content(content_url_path)
                raw = base64.b64decode(content_data["content"])
                dest.write_bytes(raw)
            except Exception as e:
                print(f"  [skip] {repo}/{path}: {e}", file=sys.stderr)
                continue
            time.sleep(0.3)

        try:
            license_id = fetch_license(repo, license_cache)
            time.sleep(0.1)
        except Exception:
            license_id = "unknown"

        fetched += 1
        attr_rows.append(
            {
                "sha": sha,
                "repo": repo,
                "path": path,
                "html_url": html_url,
                "license": license_id,
                "date_pulled": today,
            }
        )

    with attr_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sha", "repo", "path", "html_url", "license", "date_pulled"])
        writer.writeheader()
        writer.writerows(attr_rows)

    print(f"\nDone. fetched={fetched}")
    print(f"Raw YAML          -> {out_dir}")
    print(f"Attribution log   -> {attr_path}")


if __name__ == "__main__":
    main()
