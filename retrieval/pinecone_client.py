"""Pinecone index lifecycle helpers. Two indexes, never one — see
CLAUDE.md's "hybrid retrieval, two collections, not one" rule and
AGENTS.md's Structured/Prose Retriever split."""
from __future__ import annotations

from pinecone import Pinecone, ServerlessSpec

from .config import settings

_pc: Pinecone | None = None


def get_client() -> Pinecone:
    global _pc
    if _pc is None:
        settings.require_pinecone()
        _pc = Pinecone(api_key=settings.pinecone_api_key)
    return _pc


def ensure_index(name: str):
    pc = get_client()
    existing = {idx["name"] for idx in pc.list_indexes()}
    if name not in existing:
        pc.create_index(
            name=name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
        )
    return pc.Index(name)


def get_configs_index():
    return ensure_index(settings.pinecone_index_configs)


def get_prose_index():
    return ensure_index(settings.pinecone_index_prose)
