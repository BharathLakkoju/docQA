"""Phase 1e — pull API/HTTP-error Q&A from the live Stack Exchange API.

Deliberately uses the live api.stackexchange.com API, not the gated Stack
Overflow data dump, per CLAUDE.md ("the data-dump download now requires
login and agreement to terms that prohibit using the file for LLM
training"). Anonymous quota is 300 requests/day; batches questions
(pagesize=100) and uses the batched /questions/{ids}/answers endpoint so
the whole pull costs well under a dozen requests total, not one per item.

Every item is attributed per Stack Exchange's CC-BY-SA terms (author +
link back to the original question/answer) in the attributions CSV.

Output:
  data/raw/api_errors/stackexchange/{tag}.json
  data/processed/api_errors/stackexchange_attributions.csv
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

BASE = "https://api.stackexchange.com/2.3"
SITE = "stackoverflow"
TAGS = ["github-actions", "http-status-codes", "rest", "http"]
SESSION = new_session()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=15))
def _get(path: str, params: dict) -> dict:
    params = {**params, "site": SITE}
    resp = SESSION.get(f"{BASE}/{path}", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("quota_remaining", 1) <= 5:
        print(f"  [warn] Stack Exchange quota nearly exhausted: {data.get('quota_remaining')} left", file=sys.stderr)
    return data


def fetch_questions_for_tag(tag: str, per_tag: int) -> list[dict]:
    questions = []
    page = 1
    while len(questions) < per_tag:
        data = _get(
            "questions",
            {
                "order": "desc",
                "sort": "votes",
                "tagged": tag,
                "filter": "withbody",
                "pagesize": min(100, per_tag - len(questions)),
                "page": page,
            },
        )
        items = data.get("items", [])
        questions.extend(items)
        if not data.get("has_more") or not items:
            break
        page += 1
        time.sleep(0.2)
    return questions[:per_tag]


def fetch_answers_batched(question_ids: list[int]) -> dict[int, list[dict]]:
    """Batch up to 100 question ids per call via the semicolon-joined ids endpoint."""
    by_question: dict[int, list[dict]] = {}
    for i in tqdm(range(0, len(question_ids), 100), desc="fetching answers (batched)"):
        batch = question_ids[i : i + 100]
        ids_str = ";".join(str(q) for q in batch)
        data = _get(
            f"questions/{ids_str}/answers",
            {"order": "desc", "sort": "votes", "filter": "withbody", "pagesize": 100},
        )
        for a in data.get("items", []):
            by_question.setdefault(a["question_id"], []).append(a)
        time.sleep(0.3)
    return by_question


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-tag", type=int, default=120)
    parser.add_argument("--out-dir", default="data/raw/api_errors/stackexchange")
    parser.add_argument("--attributions-csv", default="data/processed/api_errors/stackexchange_attributions.csv")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attr_path = Path(args.attributions_csv)
    attr_path.parent.mkdir(parents=True, exist_ok=True)

    attr_rows = []
    today = time.strftime("%Y-%m-%d")
    total_questions = 0

    for tag in tqdm(TAGS, desc="tags"):
        questions = fetch_questions_for_tag(tag, args.per_tag)
        q_ids = [q["question_id"] for q in questions]
        answers_by_q = fetch_answers_batched(q_ids)

        for q in questions:
            q["answers"] = answers_by_q.get(q["question_id"], [])

        (out_dir / f"{tag}.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
        total_questions += len(questions)

        for q in questions:
            attr_rows.append(
                {
                    "question_id": q["question_id"],
                    "title": q.get("title", ""),
                    "author": q.get("owner", {}).get("display_name", ""),
                    "source_url": q.get("link", ""),
                    "license": q.get("content_license", "CC BY-SA 4.0"),
                    "date_pulled": today,
                }
            )
            for a in q["answers"]:
                attr_rows.append(
                    {
                        "question_id": f"{q['question_id']}#answer-{a['answer_id']}",
                        "title": f"(answer to) {q.get('title', '')}",
                        "author": a.get("owner", {}).get("display_name", ""),
                        "source_url": q.get("link", ""),
                        "license": a.get("content_license", "CC BY-SA 4.0"),
                        "date_pulled": today,
                    }
                )

    with attr_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["question_id", "title", "author", "source_url", "license", "date_pulled"])
        writer.writeheader()
        writer.writerows(attr_rows)

    print(f"\nDone. total_questions={total_questions} across tags={TAGS}")
    print(f"Raw JSON          -> {out_dir}")
    print(f"Attribution log   -> {attr_path}")


if __name__ == "__main__":
    main()
