"""Retrieval service: cosine similarity search over the pgvector embeddings."""

from app.services.retrieval.engine import (
    DEFAULT_SOURCES,
    SOURCE_SPECS,
    RetrievalEngine,
    RetrievalError,
    SourceSpec,
)
from app.services.retrieval.evidence import RetrievalEvidence, RetrievalSource

__all__ = [
    "DEFAULT_SOURCES",
    "SOURCE_SPECS",
    "RetrievalEngine",
    "RetrievalError",
    "RetrievalEvidence",
    "RetrievalSource",
    "SourceSpec",
]
