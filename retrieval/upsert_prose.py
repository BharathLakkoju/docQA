"""Phase 2 — embed + upsert the prose corpus into Pinecone.

Per INSTRUCTIONS.md Phase 2 step 2: n8n prose (1b: docs + forum) + API/HTTP
error prose (1e: Stack Exchange + MDN + IANA).

Run as: python -m retrieval.upsert_prose
"""
from __future__ import annotations

from pathlib import Path

from .pinecone_client import get_prose_index
from .upsert_common import upsert_collection

FILES = [
    Path("data/processed/n8n/prose_chunks.jsonl"),
    Path("data/processed/n8n/forum_chunks.jsonl"),
    Path("data/processed/api_errors/stackexchange_chunks.jsonl"),
    Path("data/processed/api_errors/mdn_status_chunks.jsonl"),
    Path("data/processed/api_errors/iana_status_chunks.jsonl"),
]


def main() -> None:
    index = get_prose_index()
    total = upsert_collection(index, FILES, "prose")
    print(f"\nUpserted {total} vectors into the prose index.")
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")


if __name__ == "__main__":
    main()
