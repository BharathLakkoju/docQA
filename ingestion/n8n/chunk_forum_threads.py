"""Phase 1b — chunk n8n community forum threads into question+answer prose.

Per thread: pair the opening post (the question/error report) with the
accepted answer post if one exists, else the highest-scored reply. This
mirrors INSTRUCTIONS.md 1b ("store question+accepted-answer pairs") and
keeps chunks focused on real resolved debugging exchanges rather than
raw unstructured thread dumps.

Input:  data/raw/n8n/forum/*.json
Output: data/processed/n8n/forum_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402
from common.html_text import html_to_text  # noqa: E402


def pick_answer_post(topic: dict, posts: list[dict]) -> dict | None:
    if len(posts) < 2:
        return None
    for p in posts[1:]:
        if p.get("accepted_answer") or p.get("post_number") in {
            a.get("post_number") for a in topic.get("accepted_answers", []) or []
        }:
            return p
    # no accepted answer: fall back to the reply with the highest reaction score
    replies = posts[1:]
    return max(replies, key=lambda p: p.get("score") or 0, default=None)


def chunk_topic_file(path: Path) -> dict | None:
    topic = json.loads(path.read_text(encoding="utf-8"))
    posts = topic.get("post_stream", {}).get("posts", [])
    if not posts:
        return None

    question_post = posts[0]
    answer_post = pick_answer_post(topic, posts)

    title = topic.get("title", "")
    question_text = html_to_text(question_post.get("cooked", ""))
    tags = topic.get("tags", [])
    topic_id = topic.get("id")
    slug = topic.get("slug", str(topic_id))
    url = f"https://community.n8n.io/t/{slug}/{topic_id}"

    parts = [f"# {title}", "", "## Question", question_text]
    has_accepted = bool(answer_post and answer_post.get("accepted_answer"))
    if answer_post:
        answer_text = html_to_text(answer_post.get("cooked", ""))
        label = "Accepted answer" if has_accepted else "Top reply"
        parts += ["", f"## {label}", answer_text]

    text = "\n".join(parts)
    if len(text) > 6000:
        text = text[:6000] + "\n... (truncated)"

    return {
        "id": stable_chunk_id("n8n-forum", str(topic_id)),
        "text": text,
        "metadata": {
            "domain": "n8n",
            "artifact_type": "forum_qa",
            "title": title,
            "tags": [t if isinstance(t, str) else t.get("name", "") for t in tags],
            "topic_id": topic_id,
            "source_url": url,
            "has_accepted_answer": has_accepted,
            "reply_count": len(posts) - 1,
            "source": "n8n_community_forum",
            "license": "CC-BY-SA (Stack-Exchange-style community ToS; attribute + link back)",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", default="data/raw/n8n/forum")
    parser.add_argument("--out-file", default="data/processed/n8n/forum_chunks.jsonl")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.json"))
    count = 0
    with out_file.open("w", encoding="utf-8") as out:
        for path in files:
            try:
                chunk = chunk_topic_file(path)
            except (KeyError, TypeError) as e:
                print(f"  [skip] {path.name}: {e}", file=sys.stderr)
                continue
            if chunk is None:
                continue
            out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            count += 1

    print(f"Chunked {count}/{len(files)} forum threads into Q&A prose chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
