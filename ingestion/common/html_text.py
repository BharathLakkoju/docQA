"""Shared HTML-to-plain-text conversion for Discourse/Stack Exchange `cooked`
HTML bodies. Good enough for RAG prose — not a full HTML renderer."""
from __future__ import annotations

import html
import re

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\n{3,}")


def html_to_text(cooked: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", cooked)
    text = re.sub(r"</p>", "\n\n", text)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = WS_RE.sub("\n\n", text)
    return text.strip()
