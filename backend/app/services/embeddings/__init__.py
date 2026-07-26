"""Provider-agnostic embedding service."""

from app.services.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.services.embeddings.registry import (
    available_providers,
    get_provider,
    register_provider,
)

__all__ = [
    "EmbeddingConfigurationError",
    "EmbeddingError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "available_providers",
    "get_provider",
    "register_provider",
]
