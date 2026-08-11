"""Shared result type for both retrievers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    id: str
    score: float
    text: str
    metadata: dict


def matches_to_chunks(results) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            id=match["id"],
            score=match["score"],
            text=(match.get("metadata") or {}).get("text", ""),
            metadata=match.get("metadata") or {},
        )
        for match in results.get("matches", [])
    ]
