"""Typed DTOs for the diagnosis-aware Retrieval Layer (Phase 5, Milestone 3).

All immutable frozen dataclasses. The layer returns STRUCTURED knowledge -- never
free text it generated, never an answer. A KnowledgeChunk is a unit retrieved from
a source; a RetrievedKnowledge is a chunk plus its deterministic RankingScore and
final rank; a RetrievalResult is the whole ranked, deduplicated output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

_ZERO = Decimal("0")


@dataclass(frozen=True)
class KnowledgeChunk:
    """One unit of retrievable knowledge, as returned by the vector-search layer.

    The `*_` tags (stage/industry/category/root_cause_ids) are what make retrieval
    diagnosis-aware: they let the layer pre-filter to the founder's situation and
    rank on relevance, not just cosine similarity. `source_quality` (higher =
    more authoritative) breaks ties during deduplication.
    """

    chunk_id: str
    source: str                       # e.g. "root_causes", "rag_chunks"
    source_id: int | str
    content: str
    similarity: Decimal               # vector cosine similarity, 0..1
    stage: str | None = None
    industry: str | None = None
    category: str | None = None
    root_cause_ids: tuple[int, ...] = ()
    source_quality: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalFilters:
    """Deterministic filters built from AllyContext BEFORE vector search.

    A None/empty dimension means 'do not constrain on it'. `intent` is the
    future-ready conversation-intent hook -- carried through, unused by ranking
    today, so a later milestone can use it without a schema change.
    """

    stages: tuple[str, ...] = ()
    industry: str | None = None
    root_cause_ids: tuple[int, ...] = ()
    categories: tuple[str, ...] = ()
    business_health_band: str | None = None
    distress_mode: bool = False
    min_similarity: Decimal = _ZERO
    top_k: int = 5
    intent: str | None = None


@dataclass(frozen=True)
class RetrievalRequest:
    """What the repository receives: a query plus the pre-built filters to apply
    before the vector search runs."""

    query: str
    filters: RetrievalFilters
    top_k: int


@dataclass(frozen=True)
class RankingScore:
    """The deterministic, auditable breakdown of a chunk's rank. Every component
    is 0..1; `total` is the weighted sum. Retained so a consumer can see WHY a
    chunk ranked where it did -- ranking is never a black box."""

    similarity: Decimal
    stage_match: Decimal
    industry_match: Decimal
    root_cause_relevance: Decimal
    category_relevance: Decimal
    confidence: Decimal
    total: Decimal


@dataclass(frozen=True)
class MatchBreakdown:
    """Retrieval provenance -- WHY this item was retrieved, in a consumer-facing
    shape. Every value is copied verbatim from the RankingScore the Ranker already
    computed (see `from_score`); nothing is recomputed. Purely observational
    metadata for consultant debugging, explainability, analytics and dashboards --
    it never affects ranking."""

    similarity_score: Decimal
    stage_match: Decimal
    industry_match: Decimal
    root_cause_match: Decimal
    category_match: Decimal
    confidence_multiplier: Decimal
    final_ranking_score: Decimal

    @classmethod
    def from_score(cls, score: RankingScore) -> "MatchBreakdown":
        return cls(
            similarity_score=score.similarity,
            stage_match=score.stage_match,
            industry_match=score.industry_match,
            root_cause_match=score.root_cause_relevance,
            category_match=score.category_relevance,
            confidence_multiplier=score.confidence,
            final_ranking_score=score.total,
        )


@dataclass(frozen=True)
class RetrievedKnowledge:
    chunk: KnowledgeChunk
    score: RankingScore
    rank: int
    # Provenance, derived once from `score` at construction (during ranking). It is
    # not a constructor argument, so it can never be passed inconsistently and the
    # existing RetrievedKnowledge(chunk, score, rank) call site is unchanged.
    match_breakdown: MatchBreakdown = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_breakdown", MatchBreakdown.from_score(self.score))


@dataclass(frozen=True)
class RetrievalResult:
    """The Retrieval Layer's output. Fail-closed: on any failure or when disabled,
    `items` is empty and `enabled` reflects why."""

    items: tuple[RetrievedKnowledge, ...]
    query: str
    filters: RetrievalFilters | None
    enabled: bool
    candidate_count: int              # matches from the repository (pre-dedup)
    unique_count: int                 # after deduplication

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0
