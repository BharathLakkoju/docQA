"""Shared AST-aware chunking helpers for Python source and Jupyter notebooks
(agentic_ai domain: LangGraph/AutoGen/OpenAI Agents SDK examples, Claude
Cookbooks notebooks). Structure-aware in the same spirit as the YAML/JSON
tree-walking used for n8n nodes and GitHub Actions jobs elsewhere in
ingestion/ — here the tree is a Python AST or a notebook's cell list, and
the chunk boundary is a top-level function/class or a single cell, never a
mid-function/mid-cell cut.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

MAX_CHUNK_CHARS = 4000

# Cells that are just install/setup boilerplate carry no agentic-pattern
# signal worth indexing.
_TRIVIAL_CODE_PREFIXES = ("!pip", "%pip", "!wget", "!curl", "%load_ext", "%%capture")


def chunk_python_source(text: str) -> list[tuple[str, str]]:
    """Split a Python module into (name, source) chunks at top-level
    function/class boundaries. Falls back to the whole file as one chunk
    if it has no top-level def/class (e.g. a flat script) or fails to parse
    (real-world example code sometimes uses syntax this project's Python
    version can't parse, e.g. a newer match-statement feature — skip
    rather than crash)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    units: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            segment = ast.get_source_segment(text, node)
            if segment:
                units.append((node.name, segment[:MAX_CHUNK_CHARS]))

    if units:
        return units
    stripped = text.strip()
    if not stripped:
        return []
    return [("module", stripped[:MAX_CHUNK_CHARS])]


def _cell_source(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else str(src)


def extract_notebook_code_cells(nb_path: Path) -> list[str]:
    """Return non-trivial code-cell sources from a .ipynb file, one chunk
    unit per cell (a notebook cell is already a coherent unit-of-behavior,
    same philosophy as one node/one job elsewhere)."""
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return []

    out = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = _cell_source(cell).strip()
        if len(src) < 20 or src.startswith(_TRIVIAL_CODE_PREFIXES):
            continue
        out.append(src[:MAX_CHUNK_CHARS])
    return out


def extract_notebook_markdown_text(nb_path: Path) -> str:
    """Concatenate a notebook's markdown-cell sources into one prose blob,
    ready for common/prose_chunking.py's split_paragraphs/pack_into_windows."""
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return ""

    parts = [
        _cell_source(cell).strip()
        for cell in nb.get("cells", [])
        if cell.get("cell_type") == "markdown" and _cell_source(cell).strip()
    ]
    return "\n\n".join(parts)
