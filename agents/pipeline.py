"""Wires the AGENTS.md interaction diagram together: Query Router ->
retrievers -> Answer Generator or Fix Agent. This is the one function the
FastAPI backend calls per request; each stage stays independently testable
(see retrieval/test_query_router.py, retrieval/smoke_test_retrievers.py)
so the Eval Agent (Phase 4) can probe stages separately too.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.answer_generator import AnswerResult, generate_answer  # noqa: E402
from agents.fix_agent import FixResult, generate_fix  # noqa: E402
from retrieval import prose_retriever, structured_retriever  # noqa: E402
from retrieval.query_router import RouterResult, route  # noqa: E402
from retrieval.result_types import RetrievedChunk  # noqa: E402

TOP_K = 5

# See retrieval/structured_retriever.py's module docstring for why this
# exists: factual/fix queries want real config (node/job) chunks, error
# diagnosis wants the failure corpus — an unfiltered query lets failure
# chunks crowd out job chunks for factual "what does X do" style queries.
ARTIFACT_TYPES_BY_TASK = {
    "factual_lookup": ["workflow_node", "workflow_job"],
    "fix_generation": ["workflow_node", "workflow_job"],
    "error_diagnosis": ["failed_run", "workflow_node", "workflow_job"],
}


@dataclass
class PipelineResult:
    router: RouterResult
    answer: AnswerResult | None = None
    fix: FixResult | None = None
    # Retrieved chunks are exposed (not just consumed internally) so the
    # Eval Agent can score retrieval quality independently of generation
    # quality, per AGENTS.md's Eval Agent spec.
    structured_chunks: list[RetrievedChunk] = None  # type: ignore[assignment]
    prose_chunks: list[RetrievedChunk] = None  # type: ignore[assignment]


def handle_query(query: str) -> PipelineResult:
    router_result = route(query)
    structured_domain = router_result.domain if router_result.domain in ("n8n", "github_actions") else None
    prose_domain = router_result.domain if router_result.domain in ("n8n", "api_errors") else None
    artifact_types = ARTIFACT_TYPES_BY_TASK.get(router_result.task_type)

    if router_result.needs_fix_generation:
        structured_chunks = structured_retriever.query(
            query, domain=structured_domain, top_k=TOP_K, artifact_types=artifact_types
        )
        prose_chunks = prose_retriever.query(query, domain=prose_domain, top_k=3)
        fix_result = generate_fix(query, router_result.domain, structured_chunks, prose_chunks)  # type: ignore[arg-type]
        return PipelineResult(
            router=router_result, fix=fix_result, structured_chunks=structured_chunks, prose_chunks=prose_chunks
        )

    prose_chunks = prose_retriever.query(query, domain=prose_domain, top_k=TOP_K)
    structured_chunks = (
        structured_retriever.query(query, domain=structured_domain, top_k=3, artifact_types=artifact_types)
        if structured_domain
        else []
    )
    answer_result = generate_answer(query, structured_chunks, prose_chunks)
    return PipelineResult(
        router=router_result, answer=answer_result, structured_chunks=structured_chunks, prose_chunks=prose_chunks
    )
