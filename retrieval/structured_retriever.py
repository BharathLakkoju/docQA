"""AGENTS.md Structured Retriever — queries the Pinecone "configs" index
holding AST/structure-chunked n8n workflow nodes and GitHub Actions jobs
(+ GHA failure-run chunks, see upsert_configs.py for that placement call).

artifact_types filtering exists because of a real retrieval-quality finding
during Phase 2 manual verification: GitHub Actions "what does X do" queries
were retrieving ONLY failed_run chunks, never workflow_job chunks — not
because the job chunks embed badly (a direct artifact_type-filtered probe
showed them scoring 0.77-0.78, close behind failed_run's 0.78-0.79), but
because there are ~3x more failure chunks (1,419) than job chunks (524),
and the failure chunks' terse "- uses: actions/checkout@v4" step listings
are lexically dense in exactly the action names factual queries mention,
so they crowd out job chunks in an unfiltered top-k. Task-type-aware
filtering (see agents/pipeline.py) routes factual_lookup/fix_generation
toward workflow_node/workflow_job chunks and error_diagnosis toward
failed_run, which is also the semantically correct behavior, not just a
workaround.
"""
from __future__ import annotations

from .embeddings import embed_query
from .pinecone_client import get_configs_index
from .result_types import RetrievedChunk, matches_to_chunks

_index = None


def _get_index():
    global _index
    if _index is None:
        _index = get_configs_index()
    return _index


def query(
    query_text: str,
    domain: str | None = None,
    top_k: int = 5,
    strict: bool = False,
    artifact_types: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Retrieve top-k structured chunks.

    `domain` is a soft hint (n8n / github_actions): if a filtered query
    returns fewer than top_k results and strict=False, a broader query
    fills the gap rather than silently under-returning.

    `artifact_types` restricts to specific chunk kinds (workflow_node,
    workflow_job, failed_run) — see module docstring for why this matters.
    """
    index = _get_index()
    vector = embed_query(query_text)

    conditions = []
    if domain:
        conditions.append({"domain": {"$eq": domain}})
    if artifact_types:
        conditions.append({"artifact_type": {"$in": artifact_types}})
    filter_ = {"$and": conditions} if len(conditions) > 1 else (conditions[0] if conditions else None)

    results = index.query(vector=vector, top_k=top_k, filter=filter_, include_metadata=True)
    chunks = matches_to_chunks(results)

    if filter_ and not strict and len(chunks) < top_k:
        seen_ids = {c.id for c in chunks}
        domain_only_filter = {"domain": {"$eq": domain}} if domain else None
        fallback = index.query(vector=vector, top_k=top_k, filter=domain_only_filter, include_metadata=True)
        for c in matches_to_chunks(fallback):
            if c.id not in seen_ids and len(chunks) < top_k:
                chunks.append(c)
                seen_ids.add(c.id)

    return chunks
