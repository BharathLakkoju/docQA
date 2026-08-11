"""Deterministic chunk ID helpers shared by every ingestion module.

Pinecone upserts are idempotent on vector ID, so IDs must be stable across
re-runs of the same ingestion script (same source item -> same ID), not
freshly randomized each time.
"""
import hashlib


def stable_chunk_id(*parts: str) -> str:
    """Build a stable, filesystem/Pinecone-safe ID from ordered parts."""
    raw = "::".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    prefix = "-".join(str(p) for p in parts[:2] if p)[:40]
    prefix = "".join(c if c.isalnum() or c in "-_" else "_" for c in prefix)
    return f"{prefix}-{digest}"
