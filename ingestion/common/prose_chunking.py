"""Shared semantic-chunking helpers for Markdown prose sources (n8n docs,
MDN reference pages): YAML-frontmatter parsing + paragraph-packed token
windows. Structured config chunking (n8n nodes, GH Actions jobs) has its
own AST-boundary logic elsewhere — this module is prose-only.
"""
from __future__ import annotations

import re

import tiktoken
from ruamel.yaml import YAML

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
ENC = tiktoken.get_encoding("cl100k_base")
YAML_PARSER = YAML(typ="safe")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = YAML_PARSER.load(m.group(1)) or {}
    except Exception:
        meta = {}
    return meta, text[m.end():]


def split_paragraphs(body: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body)]
    return [p for p in paras if p]


def _trailing_overlap(paragraphs: list[str], overlap_tokens: int) -> list[str]:
    """Return the trailing paragraphs of `paragraphs` whose combined token
    count is <= overlap_tokens, to carry as context into the next window."""
    overlap: list[str] = []
    total = 0
    for p in reversed(paragraphs):
        t = len(ENC.encode(p))
        if total + t > overlap_tokens:
            break
        overlap.insert(0, p)
        total += t
    return overlap


def pack_into_windows(paragraphs: list[str], chunk_tokens: int = 600, overlap_tokens: int = 100) -> list[str]:
    """Greedily pack paragraphs into ~chunk_tokens windows, carrying
    ~overlap_tokens of trailing paragraphs into the next window."""
    windows: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = len(ENC.encode(para))
        if current and current_tokens + para_tokens > chunk_tokens:
            windows.append("\n\n".join(current))
            current = _trailing_overlap(current, overlap_tokens)
            current_tokens = sum(len(ENC.encode(p)) for p in current)
        current.append(para)
        current_tokens += para_tokens

    if current:
        windows.append("\n\n".join(current))
    return windows
