"""Phase 1a — AST/structure-aware chunking of n8n workflow JSON pulled from
the official template API (fetch_templates.py).

Chunk boundary = one node (never a mid-node cut). See node_chunking.py for
the shared chunk-shape logic used by both this script and
chunk_mirror_templates.py.

Input:  data/raw/n8n/templates/*.json   (from fetch_templates.py)
Output: data/processed/n8n/structured_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from node_chunking import chunk_workflow

SOURCE = "n8n_template_api"
LICENSE = "individual template author (see ATTRIBUTIONS.md); public n8n.io template library"


def chunk_template_file(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    wf_wrapper = raw.get("workflow", {})
    inner = wf_wrapper.get("workflow", {})
    if not inner.get("nodes"):
        return []

    template_id = wf_wrapper.get("id")
    template_name = wf_wrapper.get("name", "")
    categories = [c.get("name") for c in wf_wrapper.get("categories", []) if c.get("name")]
    source_url = f"https://n8n.io/workflows/{template_id}"

    return chunk_workflow(inner, template_id, template_name, categories, SOURCE, source_url, LICENSE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", default="data/raw/n8n/templates")
    parser.add_argument("--out-file", default="data/processed/n8n/structured_chunks.jsonl")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.json"))
    total_chunks = 0
    total_templates = 0
    with out_file.open("w", encoding="utf-8") as out:
        for path in files:
            try:
                chunks = chunk_template_file(path)
            except (KeyError, TypeError) as e:
                print(f"  [skip] {path.name}: malformed workflow JSON ({e})", file=sys.stderr)
                continue
            if not chunks:
                continue
            total_templates += 1
            for chunk in chunks:
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Chunked {total_templates}/{len(files)} templates into {total_chunks} node chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
