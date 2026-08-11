"""Phase 1e — chunk MDN's HTTP status code reference pages.

Source: mdn/content, files/en-us/web/http/reference/status/**/index.md
(sparse-checked-out). CC-BY-SA 2.5. Most pages are short enough to be a
single chunk; the shared paragraph-packer in common/prose_chunking.py
handles the rare long ones the same way the n8n docs chunker does.

Output: data/processed/api_errors/mdn_status_chunks.jsonl
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

MACRO_RE = re.compile(r"\{\{[^}]*\}\}")


def strip_mdn_macros(body: str) -> str:
    # MDN KumaScript macros like {{HTTPStatus("410")}}, {{Specifications}} render nothing useful as plain text.
    return MACRO_RE.sub("", body)


def chunk_status_file(path: Path, root: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(raw)
    body = strip_mdn_macros(body)
    paragraphs = split_paragraphs(body)
    if not paragraphs:
        return []

    rel_path = path.relative_to(root).as_posix()
    status_code = path.parent.name  # e.g. "404"
    title = meta.get("title") or f"HTTP {status_code}"
    slug = meta.get("slug", "")
    url = f"https://developer.mozilla.org/en-US/docs/{slug}" if slug else ""

    windows = pack_into_windows(paragraphs)
    chunks = []
    for i, window in enumerate(windows):
        if not window.strip():
            continue
        chunks.append(
            {
                "id": stable_chunk_id("mdn-status", status_code, str(i)),
                "text": f"# {title}\n\n{window}",
                "metadata": {
                    "domain": "api_errors",
                    "artifact_type": "http_status_reference",
                    "title": title,
                    "status_code": status_code,
                    "source_path": rel_path,
                    "source_url": url,
                    "chunk_index": i,
                    "source": "mdn_content",
                    "license": "CC-BY-SA 2.5",
                },
            }
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-dir", default="data/raw/api_errors/mdn-content/files/en-us/web/http/reference/status")
    parser.add_argument("--out-file", default="data/processed/api_errors/mdn_status_chunks.jsonl")
    args = parser.parse_args()

    root = Path(args.status_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(root.glob("*/index.md"))
    total_chunks = 0
    with out_file.open("w", encoding="utf-8") as out:
        for path in files:
            for chunk in chunk_status_file(path, root):
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Chunked {len(files)} MDN status pages into {total_chunks} chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
