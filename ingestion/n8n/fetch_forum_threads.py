"""Phase 1b — pull n8n community forum (Discourse) error/debugging threads.

Uses the public Discourse JSON API on community.n8n.io (search.json + topic
detail .json), no auth required. Targets threads that look like real
error/debugging Q&A (stack traces, AxiosError, HTTP status codes, timeouts,
etc.) since that's the highest-value content for a debugging copilot, per
INSTRUCTIONS.md 1b.

Output:
  data/raw/n8n/forum/{topic_id}.json          (raw topic detail, cached)
  data/processed/n8n/forum_attributions.csv   (topic id, title, author(s), url, date)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.http import new_session  # noqa: E402

BASE = "https://community.n8n.io"
SESSION = new_session()

DEBUG_QUERIES = [
    "AxiosError",
    "status code 400",
    "status code 401",
    "status code 403",
    "status code 404",
    "status code 429",
    "status code 500",
    "webhook error",
    "workflow failed error",
    "authentication error",
    "timeout error",
    "rate limit error",
    "SSL error certificate",
    "JSON parse error",
    "ECONNREFUSED",
    "cannot connect error",
]


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=15))
def _get(url: str, params: dict | None = None) -> dict:
    resp = SESSION.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def search_topic_ids(query: str) -> list[int]:
    data = _get(f"{BASE}/search.json", {"q": query})
    return [t["id"] for t in data.get("topics", [])]


def collect_topic_ids(queries: list[int], limit: int) -> list[int]:
    seen: dict[int, None] = {}
    for q in tqdm(queries, desc="searching debug queries"):
        try:
            ids = search_topic_ids(q)
        except Exception as e:
            print(f"  [skip query] {q!r}: {e}", file=sys.stderr)
            continue
        for tid in ids:
            seen.setdefault(tid, None)
        time.sleep(0.3)
        if len(seen) >= limit:
            break
    return list(seen.keys())[:limit]


def fetch_topic(topic_id: int, out_dir: Path) -> dict | None:
    dest = out_dir / f"{topic_id}.json"
    if dest.exists():
        try:
            return json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    try:
        data = _get(f"{BASE}/t/{topic_id}.json")
    except Exception as e:
        print(f"  [skip] topic {topic_id}: {e}", file=sys.stderr)
        return None
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=400, help="max unique topics to pull")
    parser.add_argument("--out-dir", default="data/raw/n8n/forum")
    parser.add_argument("--attributions-csv", default="data/processed/n8n/forum_attributions.csv")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attr_path = Path(args.attributions_csv)
    attr_path.parent.mkdir(parents=True, exist_ok=True)

    print("Searching for error/debugging threads across queries:", DEBUG_QUERIES)
    topic_ids = collect_topic_ids(DEBUG_QUERIES, args.limit)
    print(f"Found {len(topic_ids)} unique candidate topics. Fetching full thread detail ...")

    attr_rows = []
    fetched, skipped = 0, 0
    today = time.strftime("%Y-%m-%d")
    for tid in tqdm(topic_ids, desc="fetching topics"):
        data = fetch_topic(tid, out_dir)
        time.sleep(0.2)
        if data is None:
            skipped += 1
            continue
        fetched += 1
        posts = data.get("post_stream", {}).get("posts", [])
        authors = sorted({p.get("username", "") for p in posts if p.get("username")})
        attr_rows.append(
            {
                "topic_id": tid,
                "title": data.get("title", ""),
                "authors": ";".join(authors),
                "source_url": f"{BASE}/t/{data.get('slug', tid)}/{tid}",
                "date_pulled": today,
            }
        )

    with attr_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["topic_id", "title", "authors", "source_url", "date_pulled"])
        writer.writeheader()
        writer.writerows(attr_rows)

    print(f"\nDone. fetched={fetched} skipped={skipped}")
    print(f"Raw topic JSON     -> {out_dir}")
    print(f"Attribution log    -> {attr_path}")


if __name__ == "__main__":
    main()
