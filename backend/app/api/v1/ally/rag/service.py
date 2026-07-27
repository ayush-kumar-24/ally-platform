"""Retrieval Service -- orchestration only.

Pipeline:  AllyContext -> build_filters -> repository.search (pre-filtered vector
search) -> deduplicate -> rank -> top_k -> RetrievalResult.

Strict boundaries (enforced by imports): this module imports ONLY the retrieval
package and the M1 context schema. It does NOT call an LLM, build prompts, or
touch the Prompt Manager, Memory, Router or Knowledge Graph.

Fail-closed: if the repository raises, or retrieval is disabled, it returns an
EMPTY RetrievalResult. It never fabricates knowledge.
"""

from __future__ import annotations

from decimal import Decimal

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.rag.dedup import deduplicate
from app.api.v1.ally.rag.filters import build_filters
from app.api.v1.ally.rag.ranking import Ranker, RankingWeights
from app.api.v1.ally.rag.repository import RetrievalRepository
from app.api.v1.ally.rag.schemas import (
    RetrievalFilters,
    RetrievalRequest,
    RetrievalResult,
)
from app.core.logger import logger

_ZERO = Decimal("0")


class RetrievalService:
    def __init__(
        self,
        repository: RetrievalRepository,
        *,
        ranker: Ranker | None = None,
        enabled: bool = True,
        default_top_k: int = 5,
        default_min_similarity: Decimal = _ZERO,
    ):
        self.repository = repository
        self.ranker = ranker or Ranker()
        self.enabled = enabled
        self.default_top_k = default_top_k
        self.default_min_similarity = default_min_similarity

    def retrieve(
        self,
        context: AllyContext,
        query: str,
        *,
        top_k: int | None = None,
        min_similarity: Decimal | None = None,
        intent: str | None = None,
    ) -> RetrievalResult:
        if not self.enabled:
            return self._empty(query, filters=None, enabled=False)

        top = self.default_top_k if top_k is None else max(0, top_k)
        min_sim = self.default_min_similarity if min_similarity is None else min_similarity

        filters = build_filters(context, top_k=top, min_similarity=min_sim, intent=intent)
        request = RetrievalRequest(query=query, filters=filters, top_k=top)

        try:
            candidates = tuple(self.repository.search(request))
        except Exception as exc:  # fail closed -- never fabricate knowledge
            logger.warning(
                "retrieval failed; returning empty result",
                extra={"stage": "rag_retrieval", "error": str(exc)},
            )
            return self._empty(query, filters=filters, enabled=True)

        unique = deduplicate(candidates)
        confidence = (
            context.diagnosis.overall_confidence if context.diagnosis is not None else None
        )
        ranked = self.ranker.rank(unique, filters, confidence=confidence)
        items = tuple(ranked[:top]) if top > 0 else ()

        return RetrievalResult(
            items=items,
            query=query,
            filters=filters,
            enabled=True,
            candidate_count=len(candidates),
            unique_count=len(unique),
        )

    def _empty(
        self, query: str, *, filters: RetrievalFilters | None, enabled: bool
    ) -> RetrievalResult:
        return RetrievalResult(
            items=(), query=query, filters=filters, enabled=enabled,
            candidate_count=0, unique_count=0,
        )


def build_retrieval_service(
    repository: RetrievalRepository,
    *,
    enabled: bool = True,
    default_top_k: int = 5,
    default_min_similarity: Decimal = _ZERO,
    weights: RankingWeights | None = None,
) -> RetrievalService:
    return RetrievalService(
        repository,
        ranker=Ranker(weights),
        enabled=enabled,
        default_top_k=default_top_k,
        default_min_similarity=default_min_similarity,
    )
