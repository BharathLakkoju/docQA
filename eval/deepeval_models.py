"""Wires DeepEval's LLM-as-judge and embedding model to this project's
zero-cost stack. Deliberately does NOT use DeepEval's built-in LocalModel
(single-model OpenAI-compatible wrapper) — a live test against the
project's default free OpenRouter model hit a 429 from the shared free
pool, and DeepEval's own retry policy only retries the same model. This
wrapper instead calls agents.llm_client.chat(), which already falls back
across several free models on rate-limit errors (see agents/llm_client.py
FALLBACK_MODELS) — reusing that logic rather than duplicating it.

Embeddings reuse the same fastembed model used for retrieval — never
OpenAI, per CLAUDE.md's standing constraint.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

from deepeval.models import DeepEvalBaseEmbeddingModel, DeepEvalBaseLLM
from deepeval.models.llms.utils import trim_and_load_json
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.llm_client import chat  # noqa: E402
from retrieval.config import settings  # noqa: E402
from retrieval.embeddings import embed_query, embed_texts  # noqa: E402


class OpenRouterFreeJudge(DeepEvalBaseLLM):
    """DeepEval LLM wrapper backed by agents.llm_client.chat() — free
    OpenRouter models with multi-model fallback on rate limiting."""

    def load_model(self):
        return self

    def _ask(self, prompt: str, schema: Optional[type[BaseModel]]) -> str:
        content = prompt
        if schema is not None:
            content += (
                "\n\nRespond with ONLY a single valid JSON object matching this schema, "
                f"no markdown fences, no explanation: {schema.model_json_schema()}"
            )
        return chat([{"role": "user", "content": content}], max_tokens=2500, temperature=0.0)

    def generate(self, prompt: str, schema: Optional[type[BaseModel]] = None) -> Union[str, BaseModel]:
        raw = self._ask(prompt, schema)
        if schema is None:
            return raw
        return schema.model_validate(trim_and_load_json(raw))

    async def a_generate(self, prompt: str, schema: Optional[type[BaseModel]] = None) -> Union[str, BaseModel]:
        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return f"{settings.llm_model} (via OpenRouter, free-tier fallback chain)"


def get_judge_model() -> OpenRouterFreeJudge:
    settings.require_openrouter()
    return OpenRouterFreeJudge()


class FastEmbedDeepEvalModel(DeepEvalBaseEmbeddingModel):
    def load_model(self):
        return self  # fastembed's module-level model cache in retrieval.embeddings does the real loading

    def embed_text(self, text: str) -> List[float]:
        return embed_query(text)

    async def a_embed_text(self, text: str) -> List[float]:
        return embed_query(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return embed_texts(texts)

    async def a_embed_texts(self, texts: List[str]) -> List[List[float]]:
        return embed_texts(texts)

    def get_model_name(self) -> str:
        return settings.embedding_model
