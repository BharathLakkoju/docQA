"""Phase 1e — chunk Stack Exchange Q&A into question+top-answer prose.

Mirrors the n8n forum chunker's pairing approach: accepted answer if one
exists, else the highest-voted answer. Every chunk's metadata carries the
author + link-back required by Stack Exchange's CC-BY-SA terms.

Input:  data/raw/api_errors/stackexchange/{tag}.json  (from fetch_stackexchange.py)
Output: data/processed/api_errors/stackexchange_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402
from common.html_text import html_to_text  # noqa: E402


def pick_answer(answers: list[dict]) -> dict | None:
    if not answers:
        return None
    accepted = [a for a in answers if a.get("is_accepted")]
    if accepted:
        return accepted[0]
    return max(answers, key=lambda a: a.get("score", 0))


def chunk_question(q: dict, tag: str) -> dict:
    title = q.get("title", "")
    question_text = html_to_text(q.get("body", ""))
    answer = pick_answer(q.get("answers", []))

    parts = [f"# {title}", "", "## Question", question_text]
    has_accepted = bool(answer and answer.get("is_accepted"))
    if answer:
        label = "Accepted answer" if has_accepted else "Top-voted answer"
        parts += ["", f"## {label}", html_to_text(answer.get("body", ""))]

    text = "\n".join(parts)
    if len(text) > 6000:
        text = text[:6000] + "\n... (truncated)"

    return {
        "id": stable_chunk_id("se-question", str(q["question_id"])),
        "text": text,
        "metadata": {
            "domain": "api_errors",
            "artifact_type": "stackexchange_qa",
            "title": title,
            "tag": tag,
            "tags": q.get("tags", []),
            "question_id": q["question_id"],
            "author": q.get("owner", {}).get("display_name", ""),
            "answer_author": (answer or {}).get("owner", {}).get("display_name", ""),
            "source_url": q.get("link", ""),
            "has_accepted_answer": has_accepted,
            "score": q.get("score", 0),
            "source": "stackexchange_api",
            "license": q.get("content_license", "CC BY-SA 4.0"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", default="data/raw/api_errors/stackexchange")
    parser.add_argument("--out-file", default="data/processed/api_errors/stackexchange_chunks.jsonl")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with out_file.open("w", encoding="utf-8") as out:
        for path in sorted(in_dir.glob("*.json")):
            tag = path.stem
            questions = json.loads(path.read_text(encoding="utf-8"))
            for q in questions:
                out.write(json.dumps(chunk_question(q, tag), ensure_ascii=False) + "\n")
                total += 1

    print(f"Chunked {total} Stack Exchange questions -> {out_file}")


if __name__ == "__main__":
    main()
