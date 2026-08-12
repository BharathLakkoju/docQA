"""agentic_ai domain — chunking of Model Context Protocol JSON schema
content, from modelcontextprotocol/modelcontextprotocol's `schema/`
directory (the actual protocol spec, Apache-2.0/MIT per the repo's
licensing-transition note — see ATTRIBUTIONS.md).

Two structured sources, both already atomic units-of-behavior so no
sub-splitting logic is needed (same one-chunk-per-node/job philosophy,
applied to a JSON tree instead of YAML):
  1. `schema/<version>/schema.json`'s `$defs` — one chunk per type
     definition (`CallToolRequest`, `Tool`, `Resource`, ...), 155 of them
     in the latest version.
  2. `schema/<version>/examples/<Category>/*.json` — one chunk per
     concrete request/response example, 129 of them.

Output: data/processed/agentic_ai/mcp_schema_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402

SPEC_VERSION = "2026-07-28"
REPO = "modelcontextprotocol/modelcontextprotocol"
LICENSE = "Apache-2.0"


def chunk_definitions(schema_path: Path, repo_root: Path) -> list[dict]:
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    defs = data.get("$defs") or data.get("definitions") or {}
    rel_path = schema_path.relative_to(repo_root).as_posix()
    url = f"https://github.com/{REPO}/blob/main/{rel_path}"

    chunks = []
    for name, definition in defs.items():
        text = f"MCP type definition '{name}' ({SPEC_VERSION} schema):\n\n{json.dumps({name: definition}, indent=2)}"
        chunks.append(
            {
                "id": stable_chunk_id("mcp-schema-def", SPEC_VERSION, name),
                "text": text,
                "metadata": {
                    "domain": "agentic_ai",
                    "artifact_type": "mcp_schema",
                    "schema_kind": "type_definition",
                    "schema_name": name,
                    "spec_version": SPEC_VERSION,
                    "source_path": rel_path,
                    "source_url": url,
                    "source": "mcp_schema_definitions",
                    "license": LICENSE,
                },
            }
        )
    return chunks


def chunk_examples(examples_dir: Path, repo_root: Path) -> list[dict]:
    chunks = []
    for path in sorted(examples_dir.rglob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        category = path.parent.name
        rel_path = path.relative_to(repo_root).as_posix()
        url = f"https://github.com/{REPO}/blob/main/{rel_path}"
        text = f"MCP example: {category} / {path.stem} ({SPEC_VERSION} spec):\n\n{json.dumps(obj, indent=2)}"
        chunks.append(
            {
                "id": stable_chunk_id("mcp-schema-example", category, path.stem),
                "text": text,
                "metadata": {
                    "domain": "agentic_ai",
                    "artifact_type": "mcp_schema",
                    "schema_kind": "example",
                    "schema_name": category,
                    "spec_version": SPEC_VERSION,
                    "source_path": rel_path,
                    "source_url": url,
                    "source": "mcp_schema_examples",
                    "license": LICENSE,
                },
            }
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="data/raw/agentic_ai/mcp")
    parser.add_argument("--out-file", default="data/processed/agentic_ai/mcp_schema_chunks.jsonl")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    schema_path = repo_root / "schema" / SPEC_VERSION / "schema.json"
    examples_dir = repo_root / "schema" / SPEC_VERSION / "examples"

    def_chunks = chunk_definitions(schema_path, repo_root) if schema_path.exists() else []
    example_chunks = chunk_examples(examples_dir, repo_root) if examples_dir.exists() else []

    total = 0
    with out_file.open("w", encoding="utf-8") as out:
        for chunk in def_chunks + example_chunks:
            out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            total += 1

    print(f"Chunked {len(def_chunks)} type definitions + {len(example_chunks)} examples = {total} mcp_schema chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
