"""Phase 2 step 4-5 standalone test script (INSTRUCTIONS.md): query the
Structured and Prose retrievers in isolation, ~10 sample queries spanning
all three domains, printed for manual quality inspection before the
generator gets built on top of them. Requires PINECONE_API_KEY in .env
(fastembed embeddings need no key) and a completed upsert
(upsert_configs.py / upsert_prose.py).

Run as: python -m retrieval.smoke_test_retrievers
"""
from __future__ import annotations

from agents.pipeline import ARTIFACT_TYPES_BY_TASK

from . import prose_retriever, structured_retriever
from .query_router import route

SAMPLE_QUERIES = [
    # n8n — factual lookup
    "What does the n8n Webhook node do?",
    "How do I use the Schedule Trigger node in n8n?",
    # n8n — error diagnosis
    "My n8n workflow throws an AxiosError with status code 400, what's wrong?",
    "Why is my n8n HTTP Request node returning a 401 Unauthorized error?",
    # n8n — fix generation
    "Fix this n8n workflow node so it correctly authenticates with Google Drive",
    # GitHub Actions — factual lookup
    "What does actions/checkout do in a GitHub Actions workflow?",
    "How do I use a matrix strategy in a GitHub Actions job?",
    # GitHub Actions — error diagnosis
    "Why does my GitHub Actions job fail with a Docker build error?",
    "My GitHub Actions workflow fails on npm test, why?",
    # GitHub Actions — fix generation
    "Fix this GitHub Actions YAML so the pytest job runs on push and pull_request",
    # API errors
    "What does HTTP status code 429 mean?",
    "What causes a 403 Forbidden error when calling a REST API?",
]


def main() -> None:
    for q in SAMPLE_QUERIES:
        result = route(q)
        print("=" * 100)
        print(f"QUERY: {q}")
        print(f"router -> domain={result.domain} task_type={result.task_type} needs_fix_generation={result.needs_fix_generation}")

        struct_domain = result.domain if result.domain in ("n8n", "github_actions") else None
        artifact_types = ARTIFACT_TYPES_BY_TASK.get(result.task_type)
        struct_hits = structured_retriever.query(q, domain=struct_domain, top_k=3, artifact_types=artifact_types)
        print(f"\n  [structured retriever] {len(struct_hits)} hits")
        for h in struct_hits:
            print(f"    score={h.score:.3f} id={h.id} domain={h.metadata.get('domain')} artifact_type={h.metadata.get('artifact_type')}")
            print(f"      {h.text[:150].replace(chr(10), ' ')}...")

        prose_domain = result.domain if result.domain in ("n8n", "api_errors") else None
        prose_hits = prose_retriever.query(q, domain=prose_domain, top_k=3)
        print(f"\n  [prose retriever] {len(prose_hits)} hits")
        for h in prose_hits:
            print(f"    score={h.score:.3f} id={h.id} domain={h.metadata.get('domain')} artifact_type={h.metadata.get('artifact_type')}")
            print(f"      {h.text[:150].replace(chr(10), ' ')}...")
        print()


if __name__ == "__main__":
    main()
