"""OpenAI Embeddings adapter.

text-embedding-3-* supports a `dimensions` parameter, so the adapter requests
exactly `EMBEDDING_DIMENSION` and reports that dimension.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.embeddings.providers._base import BaseHTTPEmbeddingProvider
from app.services.embeddings.registry import register_provider

_DEFAULT_MODEL = "text-embedding-3-small"
_LOCAL_SENTINEL = "gte-small"  # local-model default; not an OpenAI model


class OpenAIEmbeddingProvider(BaseHTTPEmbeddingProvider):
    name = "openai"

    @classmethod
    def from_settings(cls) -> "OpenAIEmbeddingProvider":
        model = settings.EMBEDDING_MODEL
        if not model or model == _LOCAL_SENTINEL:
            model = _DEFAULT_MODEL
        return cls(
            api_key=settings.OPENAI_API_KEY,
            model=model,
            dimension=settings.EMBEDDING_DIMENSION,
            base_url=settings.OPENAI_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            backoff=settings.PROVIDER_BACKOFF_SECONDS,
        )

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/embeddings"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _build_payload(self, text: str) -> dict:
        return {"model": self.model, "input": text, "dimensions": self.dimension}

    def _parse(self, data: dict) -> list[float]:
        return [float(x) for x in data["data"][0]["embedding"]]


register_provider("openai", OpenAIEmbeddingProvider.from_settings)
