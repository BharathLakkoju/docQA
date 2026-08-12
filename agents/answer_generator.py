"""AGENTS.md Answer Generator — grounded Q&A with citations.

The "decline to answer when nothing relevant was retrieved" behavior is an
explicit Python code path (checked against RELEVANCE_THRESHOLD before the
LLM is ever called), not something the prompt merely asks the model to do
— per INSTRUCTIONS.md Phase 3 step 1, this must not rely on the LLM
behaving. Citations only ever reference chunks that were actually
retrieved; nothing is invented.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.llm_client import chat  # noqa: E402
from retrieval.result_types import RetrievedChunk  # noqa: E402

# Recalibrated after a real failure: eval/run_edge_case_tests.py's out_of_corpus
# cases ("What's the weather like in Paris?", "capital of Australia?", etc.)
# were all answering confidently instead of declining. Direct measurement showed
# why 0.35 was wrong — bge-small-en-v1.5 cosine scores for genuinely unrelated
# queries against this corpus cluster at 0.46-0.53 (not near 0, an anisotropy
# characteristic of this embedding family), while genuinely relevant queries
# cluster at 0.78-0.90. 0.6 sits in the wide gap between those two clusters.
# The original 0.35 was set from a "Phase 2 manual spot check" that evidently
# never tried a truly out-of-domain query — a caution against trusting a
# threshold that hasn't been checked against negative examples.
RELEVANCE_THRESHOLD = 0.6

DECLINE_MESSAGE = (
    "I don't have enough context to answer that. Nothing in the n8n / GitHub Actions / "
    "API-error / AI agent tooling corpus I have indexed scored above the relevance threshold "
    "for this question."
)

SYSTEM_PROMPT = (
    "You are WorkflowGPT, a copilot for n8n workflows, GitHub Actions CI/CD, API/HTTP "
    "error debugging, and AI agent tooling (MCP, LangGraph, AutoGen, CrewAI, OpenAI Agents SDK, "
    "GitHub Copilot, HuggingFace, LangChain). Answer ONLY using the numbered context chunks "
    "provided below. Cite the chunk number(s) you used like [1] or [2][3] inline. "
    "If the context doesn't actually answer the question, say so plainly instead of guessing."
)


@dataclass
class Citation:
    index: int
    source_url: str
    title: str
    artifact_type: str


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    declined: bool = False


def _relevant(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    return [c for c in chunks if c.score >= RELEVANCE_THRESHOLD]


def _build_context_block(chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    lines = []
    citations = []
    for i, c in enumerate(chunks, start=1):
        title = c.metadata.get("title") or c.metadata.get("template_name") or c.metadata.get("workflow_name") or c.metadata.get("job_name") or c.id
        source_url = c.metadata.get("source_url", "")
        artifact_type = c.metadata.get("artifact_type", "")
        lines.append(f"[{i}] ({artifact_type}) {title}\n{c.text}")
        citations.append(Citation(index=i, source_url=source_url, title=title, artifact_type=artifact_type))
    return "\n\n".join(lines), citations


def generate_answer(
    query: str, structured_chunks: list[RetrievedChunk], prose_chunks: list[RetrievedChunk]
) -> AnswerResult:
    all_chunks = structured_chunks + prose_chunks
    relevant = _relevant(all_chunks)

    if not relevant:
        return AnswerResult(answer=DECLINE_MESSAGE, citations=[], declined=True)

    # Highest-scoring first so the model sees the strongest evidence up front.
    relevant.sort(key=lambda c: c.score, reverse=True)
    context_block, citations = _build_context_block(relevant)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context_block}\n\nQuestion: {query}"},
    ]
    answer_text = chat(messages, max_tokens=700, temperature=0.2)

    used_indices = {i for i in range(1, len(citations) + 1) if f"[{i}]" in answer_text}
    used_citations = [c for c in citations if c.index in used_indices] or citations

    return AnswerResult(answer=answer_text, citations=used_citations, declined=False)
