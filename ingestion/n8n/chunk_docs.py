"""Phase 1b — semantic chunking of official n8n documentation Markdown.

Source: n8n-io/n8n-docs, docs/**/*.md (cloned via sparse checkout).
Standard semantic chunking (not AST-aware — this is prose, not config):
~600 tokens per chunk, ~100 token overlap, split on paragraph boundaries so
a chunk never cuts a sentence mid-way where avoidable. See
common/prose_chunking.py for the shared frontmatter/windowing logic (also
used by the MDN HTTP-status chunker in ingestion/api_errors/).

Output: data/processed/n8n/prose_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402
from common.prose_chunking import pack_into_windows, parse_frontmatter, split_paragraphs  # noqa: E402


def strip_markdown_noise(body: str) -> str:
    # Docusaurus/GitBook hint blocks: keep the text, drop the {% %} directives.
    body = re.sub(r"\{%\s*hint[^%]*%\}", "", body)
    body = re.sub(r"\{%\s*endhint\s*%\}", "", body)
    # Anchor tags like <a href="#x" id="x"></a> inside headings add no semantic value.
    body = re.sub(r'<a href="#[^"]*" id="[^"]*"></a>', "", body)
    return body


def chunk_doc_file(path: Path, docs_root: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(raw)
    body = strip_markdown_noise(body)
    paragraphs = split_paragraphs(body)
    if not paragraphs:
        return []

    rel_path = path.relative_to(docs_root).as_posix()
    title = meta.get("title") or (paragraphs[0].lstrip("# ").split("\n")[0] if paragraphs else rel_path)
    url = meta.get("url") or f"https://docs.n8n.io/{rel_path.removesuffix('.md')}"
    section = rel_path.split("/")[0]

    windows = pack_into_windows(paragraphs)
    chunks = []
    for i, window in enumerate(windows):
        if not window.strip():
            continue
        chunks.append(
            {
                "id": stable_chunk_id("n8n-doc", rel_path, str(i)),
                "text": f"# {title}\n\n{window}",
                "metadata": {
                    "domain": "n8n",
                    "artifact_type": "doc_prose",
                    "title": title,
                    "section": section,
                    "source_path": rel_path,
                    "source_url": url,
                    "chunk_index": i,
                    "source": "n8n_io_docs",
                    "license": "Sustainable Use License (fair-code, not OSI)",
                },
            }
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-dir", default="data/raw/n8n/n8n-docs/docs")
    parser.add_argument("--out-file", default="data/processed/n8n/prose_chunks.jsonl")
    parser.add_argument(
        "--exclude-dirs",
        nargs="*",
        default=["_workflows", "changelog"],
        help="top-level docs/ subdirs to skip (changelog is release notes, not conceptual/debugging prose)",
    )
    args = parser.parse_args()

    docs_root = Path(args.docs_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    files = [
        p
        for p in sorted(docs_root.rglob("*.md"))
        if p.relative_to(docs_root).parts[0] not in args.exclude_dirs
    ]

    total_chunks = 0
    with out_file.open("w", encoding="utf-8") as out:
        for path in files:
            for chunk in chunk_doc_file(path, docs_root):
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Chunked {len(files)} doc pages into {total_chunks} prose chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
