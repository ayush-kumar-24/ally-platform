"""Provider-agnostic text-embedding interface.

Mirrors the LLM layer: the Retrieval Engine depends only on `EmbeddingProvider`,
never on a specific model runtime. A concrete gte-small adapter (Supabase edge
function, or a local sentence-transformers model) is registered separately and
selected by configuration. No adapter is imported here.

Sync by design: the retrieval enricher runs inside the synchronous reasoning
pipeline, so embedding is a blocking call. An adapter backed by a network service
performs a synchronous request.
"""

from __future__ import annotations

import abc


class EmbeddingError(Exception):
    """Base class for embedding-layer failures."""


class EmbeddingConfigurationError(EmbeddingError):
    """No provider configured, or a required setting/credential is missing."""


class EmbeddingProviderError(EmbeddingError):
    """The provider was reached but failed (upstream error, malformed output)."""


class EmbeddingProvider(abc.ABC):
    """Turns text into a fixed-dimension embedding vector.

    Implementations expose their identity (`name`, `model`, `dimension`) so the
    Retrieval Engine can assert the produced dimension matches the stored vectors
    before querying -- a mismatch means the wrong model and is caught loudly
    rather than silently returning meaningless neighbours.
    """

    #: Stable adapter id used in configuration/logging, e.g. "supabase_gte_small".
    name: str
    #: The embedding model, e.g. "gte-small".
    model: str
    #: Output dimensionality, e.g. 384.
    dimension: int

    @abc.abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single string. Raises EmbeddingProviderError on failure."""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings. Default loops `embed`; adapters may override with a
        native batch call."""
        return [self.embed(t) for t in texts]
