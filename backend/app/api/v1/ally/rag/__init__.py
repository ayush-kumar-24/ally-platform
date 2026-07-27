"""Ally diagnosis-aware Retrieval Layer (Phase 5, Milestone 3).

Given an AllyContext, it builds deterministic filters, runs a pre-filtered vector
search through a repository interface, deduplicates, and ranks on similarity PLUS
diagnosis relevance -- returning structured RetrievalResult. It never calls an LLM,
builds a prompt, or touches Memory/Router/Knowledge Graph, and fails closed to an
empty result.
"""

from app.api.v1.ally.rag.dedup import deduplicate
from app.api.v1.ally.rag.filters import build_filters
from app.api.v1.ally.rag.ranking import Ranker, RankingWeights
from app.api.v1.ally.rag.repository import (
    InMemoryVectorRetrievalRepository,
    RetrievalRepository,
    passes_filters,
)
from app.api.v1.ally.rag.schemas import (
    KnowledgeChunk,
    MatchBreakdown,
    RankingScore,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalResult,
    RetrievedKnowledge,
)
from app.api.v1.ally.rag.service import RetrievalService, build_retrieval_service

__all__ = [
    "RetrievalService",
    "build_retrieval_service",
    "RetrievalRepository",
    "InMemoryVectorRetrievalRepository",
    "passes_filters",
    "build_filters",
    "Ranker",
    "RankingWeights",
    "deduplicate",
    "KnowledgeChunk",
    "RetrievalFilters",
    "RetrievalRequest",
    "RankingScore",
    "MatchBreakdown",
    "RetrievedKnowledge",
    "RetrievalResult",
]
