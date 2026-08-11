"""AGENTS.md Prose Retriever — queries the Pinecone "prose" index holding
semantically-chunked n8n docs/forum threads and Stack Exchange/MDN/IANA
API-error content. Separate index, separate chunking strategy from the
Structured Retriever by design (see CLAUDE.md's hybrid-retrieval rule).
"""
from __future__ import annotations

from .embeddings import embed_query
from .pinecone_client import get_prose_index
from .result_types import RetrievedChunk, matches_to_chunks

_index = None


def _get_index():
    global _index
    if _index is None:
        _index = get_prose_index()
    return _index


def query(query_text: str, domain: str | None = None, top_k: int = 5, strict: bool = False) -> list[RetrievedChunk]:
    """Same soft-domain-filter behavior as structured_retriever.query — see
    its docstring. `domain` here is n8n / api_errors (github_actions has no
    dedicated prose corpus; api_errors content already covers github-actions-
    tagged Stack Exchange Q&A, see ATTRIBUTIONS.md)."""
    index = _get_index()
    vector = embed_query(query_text)

    filter_ = {"domain": {"$eq": domain}} if domain else None
    results = index.query(vector=vector, top_k=top_k, filter=filter_, include_metadata=True)
    chunks = matches_to_chunks(results)

    if domain and not strict and len(chunks) < top_k:
        seen_ids = {c.id for c in chunks}
        fallback = index.query(vector=vector, top_k=top_k, include_metadata=True)
        for c in matches_to_chunks(fallback):
            if c.id not in seen_ids and len(chunks) < top_k:
                chunks.append(c)
                seen_ids.add(c.id)

    return chunks
