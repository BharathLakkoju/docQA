"""Central settings for the retrieval layer, loaded from .env.

Every other retrieval module imports `settings` from here rather than
reading os.environ directly, so there's one place that knows the env var
names (matches .env.example).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

EMBEDDING_DIMENSIONS = {
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-small-en": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}

# BGE models are trained with an asymmetric query/passage convention: queries
# get this instruction prefix, indexed passages/chunks do not. Skipping it
# measurably hurts retrieval quality for this model family.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pinecone_api_key: str = ""
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_index_configs: str = "workflowgpt-configs"
    pinecone_index_prose: str = "workflowgpt-prose"

    # Local, free, no API key: fastembed (ONNX runtime, no PyTorch) runs
    # inside the backend itself — no OpenAI, no per-request embedding cost.
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # LLM generation goes through OpenRouter's free-tier models only —
    # never OpenAI directly, and never a paid OpenRouter model, per explicit
    # project constraint (zero cost, portfolio/demo use only).
    llm_provider: str = "openrouter"
    llm_model: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_api_key: str = ""

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    # Comma-separated list; overridden in production via env var to the deployed
    # Vercel frontend origin.
    cors_origins: str = "http://localhost:3000"

    @property
    def embedding_dimensions(self) -> int:
        return EMBEDDING_DIMENSIONS.get(self.embedding_model, 384)

    def require_pinecone(self) -> None:
        if not self.pinecone_api_key:
            raise RuntimeError(
                "PINECONE_API_KEY is not set. Copy .env.example to .env and fill it in "
                "(see the Pinecone free-tier signup at https://app.pinecone.io)."
            )

    def require_openrouter(self) -> None:
        if not self.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in "
                "(free signup at https://openrouter.ai)."
            )


settings = Settings()
