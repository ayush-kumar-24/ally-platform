"""Google Gemini Embeddings adapter (embedContent).

Newer embedding models accept `outputDimensionality`, so the adapter requests
exactly `EMBEDDING_DIMENSION` and reports that dimension.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.embeddings.providers._base import BaseHTTPEmbeddingProvider
from app.services.embeddings.registry import register_provider

_DEFAULT_MODEL = "text-embedding-004"
_LOCAL_SENTINEL = "gte-small"


class GeminiEmbeddingProvider(BaseHTTPEmbeddingProvider):
    name = "gemini"

    @classmethod
    def from_settings(cls) -> "GeminiEmbeddingProvider":
        model = settings.EMBEDDING_MODEL
        if not model or model == _LOCAL_SENTINEL:
            model = _DEFAULT_MODEL
        return cls(
            api_key=settings.GEMINI_API_KEY,
            model=model,
            dimension=settings.EMBEDDING_DIMENSION,
            base_url=settings.GEMINI_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            backoff=settings.PROVIDER_BACKOFF_SECONDS,
        )

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1beta/models/{self.model}:embedContent"

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def _build_payload(self, text: str) -> dict:
        return {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self.dimension,
        }

    def _parse(self, data: dict) -> list[float]:
        return [float(x) for x in data["embedding"]["values"]]


register_provider("gemini", GeminiEmbeddingProvider.from_settings)
