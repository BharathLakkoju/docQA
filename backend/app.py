"""FastAPI backend for WorkflowGPT / CI-CD Copilot.

Thin HTTP layer over agents/pipeline.py (the live agentic pipeline) and
eval/results/*.json (the Phase 4 eval outputs). Never recomputes or
massages eval numbers here — /eval/* just serves what run_eval.py already
wrote to disk, so the dashboard is always showing the real, disclosed
results, including the null judge scores and the by-domain gap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.pipeline import handle_query  # noqa: E402
from retrieval.config import settings  # noqa: E402

EVAL_RESULTS_DIR = ROOT / "eval" / "results"
QUESTION_SET_PATH = ROOT / "eval" / "question_set.jsonl"

app = FastAPI(title="WorkflowGPT / CI-CD Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


class CitationOut(BaseModel):
    index: int
    source_url: str
    title: str
    artifact_type: str


class ChunkOut(BaseModel):
    id: str
    score: float
    text: str
    artifact_type: str = ""
    title: str = ""
    source_url: str = ""


class RouterOut(BaseModel):
    domain: Literal["n8n", "github_actions", "api_errors"]
    task_type: Literal["factual_lookup", "error_diagnosis", "fix_generation"]
    needs_fix_generation: bool


class QueryResponse(BaseModel):
    router: RouterOut
    mode: Literal["answer", "fix"]
    answer: str | None = None
    declined: bool = False
    citations: list[CitationOut] = []
    fix_snippet: str | None = None
    validated: bool | None = None
    attempts: int | None = None
    validator_errors: list[str] = []
    structured_chunks: list[ChunkOut] = []
    prose_chunks: list[ChunkOut] = []


def _chunk_out(c) -> ChunkOut:
    return ChunkOut(
        id=c.id,
        score=c.score,
        text=c.text,
        artifact_type=c.metadata.get("artifact_type", ""),
        title=c.metadata.get("title")
        or c.metadata.get("template_name")
        or c.metadata.get("workflow_name")
        or c.metadata.get("job_name")
        or "",
        source_url=c.metadata.get("source_url", ""),
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query must not be empty")

    result = handle_query(q)
    router_out = RouterOut(
        domain=result.router.domain,
        task_type=result.router.task_type,
        needs_fix_generation=result.router.needs_fix_generation,
    )
    structured_out = [_chunk_out(c) for c in (result.structured_chunks or [])]
    prose_out = [_chunk_out(c) for c in (result.prose_chunks or [])]

    if result.fix is not None:
        return QueryResponse(
            router=router_out,
            mode="fix",
            fix_snippet=result.fix.fix_snippet,
            validated=result.fix.validated,
            attempts=result.fix.attempts,
            validator_errors=result.fix.validator_errors,
            structured_chunks=structured_out,
            prose_chunks=prose_out,
        )

    answer = result.answer
    return QueryResponse(
        router=router_out,
        mode="answer",
        answer=answer.answer if answer else None,
        declined=answer.declined if answer else False,
        citations=[
            CitationOut(index=c.index, source_url=c.source_url, title=c.title, artifact_type=c.artifact_type)
            for c in (answer.citations if answer else [])
        ],
        structured_chunks=structured_out,
        prose_chunks=prose_out,
    )


@app.get("/eval/aggregate")
def eval_aggregate() -> dict:
    path = EVAL_RESULTS_DIR / "aggregate.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no eval results found — run eval/run_eval.py first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/eval/questions")
def eval_questions() -> list[dict]:
    """Per-question eval results joined with the question text for the dashboard."""
    per_question_path = EVAL_RESULTS_DIR / "per_question.jsonl"
    if not per_question_path.exists():
        raise HTTPException(status_code=404, detail="no eval results found — run eval/run_eval.py first")

    queries_by_id: dict[str, dict] = {}
    if QUESTION_SET_PATH.exists():
        for line in QUESTION_SET_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            queries_by_id[item["id"]] = item

    rows = []
    for line in per_question_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        q = queries_by_id.get(record["id"])
        record["query"] = q["query"] if q else None
        rows.append(record)
    return rows


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port)
