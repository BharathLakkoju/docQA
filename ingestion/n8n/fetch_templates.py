"""Phase 1a — pull n8n workflow templates from the official template API.

Source: https://api.n8n.io/templates/search (paginated summaries) +
        https://api.n8n.io/templates/workflows/{id} (full importable workflow JSON).

No API key required. This is a real, live pull against a public API — every
run hits the network and writes exactly what the API returned, nothing
fabricated or interpolated.

Usage:
    python ingestion/n8n/fetch_templates.py --limit 300 --out-dir data/raw/n8n/templates
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tenacity import RetryError, retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.http import new_session  # noqa: E402

SEARCH_URL = "https://api.n8n.io/templates/search"
DETAIL_URL = "https://api.n8n.io/templates/workflows/{id}"
ROWS_PER_PAGE = 100
SESSION = new_session()


class NotFound(Exception):
    pass


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_not_exception_type(NotFound),
)
def _get(url: str, params: dict | None = None) -> dict:
    resp = SESSION.get(url, params=params, timeout=20)
    if resp.status_code == 404:
        raise NotFound(url)
    resp.raise_for_status()
    return resp.json()


def list_template_summaries(limit: int) -> list[dict]:
    """Paginate /templates/search until `limit` summaries collected (or exhausted)."""
    summaries: list[dict] = []
    page = 1
    with tqdm(total=limit, desc="listing templates") as pbar:
        while len(summaries) < limit:
            data = _get(SEARCH_URL, {"page": page, "rows": ROWS_PER_PAGE})
            batch = data.get("workflows", [])
            if not batch:
                break
            summaries.extend(batch)
            pbar.update(len(batch))
            if len(batch) < ROWS_PER_PAGE:
                break  # last page
            page += 1
    return summaries[:limit]


def fetch_one(template_id: int, out_dir: Path) -> dict | None:
    dest = out_dir / f"{template_id}.json"
    if dest.exists():
        try:
            return json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass  # corrupt cache, refetch
    try:
        data = _get(DETAIL_URL.format(id=template_id))
    except (NotFound, requests.HTTPError, requests.RequestException, RetryError) as e:
        print(f"  [skip] template {template_id}: {e}", file=sys.stderr)
        return None
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=300, help="number of templates to pull")
    parser.add_argument("--out-dir", default="data/raw/n8n/templates")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--attributions-csv",
        default="data/processed/n8n/template_attributions.csv",
        help="per-template attribution log (id, title, author, url, date)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attr_path = Path(args.attributions_csv)
    attr_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Listing up to {args.limit} template summaries from {SEARCH_URL} ...")
    summaries = list_template_summaries(args.limit)
    print(f"Got {len(summaries)} summaries. Fetching full workflow JSON for each ...")

    fetched, failed = 0, 0
    attr_rows = []
    today = time.strftime("%Y-%m-%d")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch_one, s["id"], out_dir): s for s in summaries
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="fetching workflow JSON"):
            summary = futures[fut]
            data = fut.result()
            if data is None:
                failed += 1
                continue
            fetched += 1
            user = summary.get("user") or {}
            attr_rows.append(
                {
                    "template_id": summary["id"],
                    "title": summary.get("name", ""),
                    "author": user.get("name", "") or user.get("username", ""),
                    "source_url": f"https://n8n.io/workflows/{summary['id']}",
                    "date_pulled": today,
                }
            )

    with attr_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["template_id", "title", "author", "source_url", "date_pulled"])
        writer.writeheader()
        writer.writerows(attr_rows)

    print(f"\nDone. fetched={fetched} failed={failed}")
    print(f"Raw workflow JSON -> {out_dir}")
    print(f"Attribution log   -> {attr_path}")


if __name__ == "__main__":
    main()
