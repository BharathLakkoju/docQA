"""agentic_ai domain — AST-aware chunking of Python example code and
Jupyter notebooks across four sources (openai-agents-python, langgraph,
autogen, claude-cookbooks). Chunk boundary = one top-level function/class
(for .py files, via ast.parse) or one cell (for .ipynb files) — see
ingestion/common/code_chunking.py for the shared helpers, and its
module docstring for why this needed new logic rather than reusing the
YAML/JSON tree-walking chunkers elsewhere in ingestion/.

Notebooks interleave code and prose in one file, so this script produces
BOTH outputs in a single pass rather than running a separate prose chunker
over the same file twice:
  - code cells / top-level functions/classes -> agent_code_chunks.jsonl
  - markdown cells -> notebook_doc_prose_chunks.jsonl (merged into the
    domain=agentic_ai doc_prose collection alongside chunk_docs.py's output)

Output:
  data/processed/agentic_ai/agent_code_chunks.jsonl
  data/processed/agentic_ai/notebook_doc_prose_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402
from common.code_chunking import (  # noqa: E402
    chunk_python_source,
    extract_notebook_code_cells,
    extract_notebook_markdown_text,
)
from common.prose_chunking import pack_into_windows, split_paragraphs  # noqa: E402


@dataclass
class PySource:
    name: str
    root: Path
    repo: str
    license: str


@dataclass
class NotebookSource:
    name: str
    root: Path
    repo: str
    license: str


PY_SOURCES = [
    PySource(
        name="openai_agents_sdk_examples",
        root=Path("data/raw/agentic_ai/openai-agents-python/examples"),
        repo="openai/openai-agents-python",
        license="MIT",
    ),
    PySource(
        name="autogen_examples",
        root=Path("data/raw/agentic_ai/autogen/python/samples"),
        repo="microsoft/autogen",
        license="MIT",
    ),
    PySource(
        name="autogen_ext_examples",
        root=Path("data/raw/agentic_ai/autogen/python/packages/autogen-ext/examples"),
        repo="microsoft/autogen",
        license="MIT",
    ),
]

NOTEBOOK_SOURCES = [
    NotebookSource(
        name="langgraph_examples",
        root=Path("data/raw/agentic_ai/langgraph/examples"),
        repo="langchain-ai/langgraph",
        license="MIT",
    ),
    NotebookSource(
        name="autogen_notebooks",
        root=Path("data/raw/agentic_ai/autogen/python"),
        repo="microsoft/autogen",
        license="MIT",
    ),
    NotebookSource(
        name="claude_cookbooks",
        root=Path("data/raw/agentic_ai/claude-cookbooks"),
        repo="anthropics/claude-cookbooks",
        license="MIT",
    ),
]


def blob_url(repo: str, rel_path: str) -> str:
    return f"https://github.com/{repo}/blob/main/{rel_path}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="data/raw/agentic_ai")
    parser.add_argument("--out-code-file", default="data/processed/agentic_ai/agent_code_chunks.jsonl")
    parser.add_argument("--out-prose-file", default="data/processed/agentic_ai/notebook_doc_prose_chunks.jsonl")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    out_code_file = Path(args.out_code_file)
    out_prose_file = Path(args.out_prose_file)
    out_code_file.parent.mkdir(parents=True, exist_ok=True)

    code_chunks_total = 0
    prose_chunks_total = 0

    with out_code_file.open("w", encoding="utf-8") as code_out, out_prose_file.open("w", encoding="utf-8") as prose_out:
        # --- Plain .py example sources ---
        for src in PY_SOURCES:
            if not src.root.exists():
                print(f"  [skip] {src.name}: root {src.root} not found", file=sys.stderr)
                continue
            files = sorted(src.root.rglob("*.py"))
            src_code = 0
            for path in files:
                if path.name == "__init__.py":
                    continue
                rel_path = path.relative_to(repo_root).as_posix()
                text = path.read_text(encoding="utf-8", errors="replace")
                for unit_name, segment in chunk_python_source(text):
                    chunk = {
                        "id": stable_chunk_id("agent-code-py", src.name, rel_path, unit_name),
                        "text": f"# from {rel_path} ({src.name})\n\n{segment}",
                        "metadata": {
                            "domain": "agentic_ai",
                            "artifact_type": "agent_code",
                            "code_kind": "python_function_or_class",
                            "unit_name": unit_name,
                            "source_path": rel_path,
                            "source_url": blob_url(src.repo, rel_path),
                            "source": src.name,
                            "license": src.license,
                        },
                    }
                    code_out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    src_code += 1
            code_chunks_total += src_code
            print(f"{src.name}: {len(files)} .py files -> {src_code} agent_code chunks")

        # --- Notebook sources: code cells -> agent_code, markdown cells -> doc_prose ---
        for src in NOTEBOOK_SOURCES:
            if not src.root.exists():
                print(f"  [skip] {src.name}: root {src.root} not found", file=sys.stderr)
                continue
            files = sorted(src.root.rglob("*.ipynb"))
            src_code = 0
            src_prose = 0
            for path in files:
                if ".ipynb_checkpoints" in path.parts:
                    continue
                rel_path = path.relative_to(repo_root).as_posix()
                url = blob_url(src.repo, rel_path)

                for i, cell_src in enumerate(extract_notebook_code_cells(path)):
                    chunk = {
                        "id": stable_chunk_id("agent-code-nb", src.name, rel_path, str(i)),
                        "text": f"# from {rel_path} ({src.name}), code cell {i}\n\n{cell_src}",
                        "metadata": {
                            "domain": "agentic_ai",
                            "artifact_type": "agent_code",
                            "code_kind": "notebook_cell",
                            "unit_name": f"cell_{i}",
                            "source_path": rel_path,
                            "source_url": url,
                            "source": src.name,
                            "license": src.license,
                        },
                    }
                    code_out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    src_code += 1

                md_text = extract_notebook_markdown_text(path)
                paragraphs = split_paragraphs(md_text)
                if not paragraphs:
                    continue
                title = paragraphs[0].lstrip("# ").split("\n")[0][:120] if paragraphs else path.stem
                for j, window in enumerate(pack_into_windows(paragraphs)):
                    if not window.strip():
                        continue
                    chunk = {
                        "id": stable_chunk_id("nb-doc-prose", src.name, rel_path, str(j)),
                        "text": f"# {title}\n\n{window}",
                        "metadata": {
                            "domain": "agentic_ai",
                            "artifact_type": "doc_prose",
                            "title": title,
                            "source_path": rel_path,
                            "source_url": url,
                            "chunk_index": j,
                            "source": src.name,
                            "license": src.license,
                        },
                    }
                    prose_out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    src_prose += 1

            code_chunks_total += src_code
            prose_chunks_total += src_prose
            print(f"{src.name}: {len(files)} notebooks -> {src_code} agent_code + {src_prose} doc_prose chunks")

    print(f"\nTotal agent_code chunks: {code_chunks_total}")
    print(f"Total notebook doc_prose chunks: {prose_chunks_total}")
    print(f"-> {out_code_file}")
    print(f"-> {out_prose_file}")


if __name__ == "__main__":
    main()
