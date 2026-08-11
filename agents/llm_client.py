"""Shared OpenRouter chat-completion client for the Answer Generator and Fix
Agent. Free-tier OpenRouter models sit behind a shared rate-limited pool
(we hit a live 429 on the first model tried during setup), so this client
retries transient failures and falls back across a short list of other
free models rather than hard-failing the whole request on one model's
momentary congestion.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openai import OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieval.config import settings  # noqa: E402

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Free-model fallback order, verified reachable during setup (2026-08-11).
# Free-model availability on OpenRouter changes over time — re-check via
# GET https://openrouter.ai/api/v1/models (filter id.endswith(":free"))
# if every model here starts failing.
FALLBACK_MODELS = [
    settings.llm_model,
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings.require_openrouter()
        _client = OpenAI(api_key=settings.openrouter_api_key, base_url=OPENROUTER_BASE_URL)
    return _client


class EmptyCompletion(Exception):
    """OpenRouter occasionally returns a 200 response with choices=null when
    an upstream provider partial-fails without raising a proper HTTP error
    (found via a real, intermittent-not-reproducible-on-demand failure
    during Phase 4 eval — a raw request/response dump confirmed choices was
    genuinely None, not the SDK's fault). Treated like a rate limit: move to
    the next fallback model rather than crash on resp.choices[0]."""


@retry(
    # A single attempt per model: on a free-tier 429, moving straight to the
    # next fallback model is faster than waiting out this model's backoff
    # (observed empirically during Phase 4 eval — see run_eval.py timing).
    retry=retry_if_exception_type((RateLimitError, EmptyCompletion)),
    stop=stop_after_attempt(1),
    wait=wait_exponential(multiplier=1, min=1, max=2),
)
def _try_model(client: OpenAI, model: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
    resp = client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature
    )
    if not resp.choices:
        raise EmptyCompletion(f"{model} returned no choices (raw response: {resp.model_dump_json()[:500]})")
    return resp.choices[0].message.content or ""


def chat(messages: list[dict], max_tokens: int = 800, temperature: float = 0.2) -> str:
    """Chat completion with fallback across FALLBACK_MODELS on rate-limit/empty-completion errors."""
    client = _get_client()
    models_tried = []
    last_error: Exception | None = None

    for model in dict.fromkeys(FALLBACK_MODELS):  # dedupe, preserve order
        models_tried.append(model)
        try:
            return _try_model(client, model, messages, max_tokens, temperature)
        except (RateLimitError, EmptyCompletion) as e:
            last_error = e
            continue

    raise RuntimeError(
        f"All free OpenRouter models are rate-limited or returning empty completions right now "
        f"(tried {models_tried}). Last error: {last_error}"
    )
