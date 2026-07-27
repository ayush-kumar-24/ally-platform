"""Retrieval Repository -- abstract access to vector search.

Loading/searching only: given a RetrievalRequest, apply the pre-filters and return
candidate chunks with their similarity. It performs NO ranking, NO deduplication
and NO business logic -- those belong to the service. The interface is the seam a
production DbVectorRetrievalRepository (wrapping the existing frozen
services/retrieval engine + an embedding provider) plugs into without changing the
service; hybrid vector+full-text search is a repository concern too.

`InMemoryVectorRetrievalRepository` is the default used by the tests: it applies
the same deterministic pre-filter semantics a SQL WHERE clause would.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable

from app.api.v1.ally.rag.schemas import (
    KnowledgeChunk,
    RetrievalFilters,
    RetrievalRequest,
)


class RetrievalRepository(abc.ABC):
    @abc.abstractmethod
    def search(self, request: RetrievalRequest) -> tuple[KnowledgeChunk, ...]:
        """Pre-filtered candidate chunks for the request. Implementations must
        apply the request filters BEFORE the vector search."""
        raise NotImplementedError


def passes_filters(chunk: KnowledgeChunk, f: RetrievalFilters) -> bool:
    """Diagnosis-aware pre-filter. A chunk is kept when, on every constrained
    dimension, it either matches or is unspecified (stage-agnostic / general
    knowledge is never wrongly excluded); it is dropped when it is tagged for a
    DIFFERENT stage, industry, category or an unrelated root cause."""
    if chunk.similarity < f.min_similarity:
        return False
    if f.stages and chunk.stage is not None and chunk.stage not in f.stages:
        return False
    if f.industry and chunk.industry is not None and chunk.industry != f.industry:
        return False
    if f.categories and chunk.category is not None and chunk.category not in f.categories:
        return False
    if (
        f.root_cause_ids
        and chunk.root_cause_ids
        and not (set(chunk.root_cause_ids) & set(f.root_cause_ids))
    ):
        return False
    return True


class InMemoryVectorRetrievalRepository(RetrievalRepository):
    """Holds chunks in memory and applies the pre-filter deterministically. Source
    of truth for tests; also a valid production impl for a small static corpus."""

    def __init__(self, chunks: Iterable[KnowledgeChunk]):
        self._chunks = tuple(chunks)

    def search(self, request: RetrievalRequest) -> tuple[KnowledgeChunk, ...]:
        matched = [c for c in self._chunks if passes_filters(c, request.filters)]
        # Deterministic candidate order (highest similarity first, then id).
        matched.sort(key=lambda c: (-c.similarity, c.chunk_id))
        return tuple(matched)
