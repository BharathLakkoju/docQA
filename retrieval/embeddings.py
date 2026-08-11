"""Embedding client wrapper — local, free, no API key.

Uses fastembed (ONNX Runtime, not PyTorch) so the same code that builds the
index also runs inside the deployed FastAPI backend at query time without
needing a GPU or a paid embeddings API. See config.py for why (zero-cost
deployment constraint) and BGE_QUERY_PREFIX for the query/passage asymmetry
this model family expects.
"""
from __future__ import annotations

from .config import BGE_QUERY_PREFIX, settings

_model = None


def _get_model():
    global _model
    if _model is None:
        if settings.embedding_provider != "fastembed":
            raise NotImplementedError(f"embedding provider {settings.embedding_provider!r} not implemented")
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of passages/chunks (no query prefix — see BGE_QUERY_PREFIX)."""
    model = _get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    model = _get_model()
    prefixed = f"{BGE_QUERY_PREFIX}{text}" if "bge" in settings.embedding_model.lower() else text
    return next(model.embed([prefixed])).tolist()
