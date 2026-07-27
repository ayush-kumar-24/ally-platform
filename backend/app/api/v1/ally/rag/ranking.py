"""Ranking Layer -- deterministic relevance scoring AFTER retrieval.

Vector similarity alone is not enough for a diagnosis-aware system: a chunk about
the founder's actual stage, industry and root causes should outrank a
semantically-similar but situationally-irrelevant one. So the total score is a
weighted sum of similarity plus diagnosis-relevance signals, every component 0..1:

    total = w_similarity * similarity
          + w_stage      * stage_match
          + w_industry   * industry_match
          + confidence   * ( w_root_cause * root_cause_relevance
                           + w_category   * category_relevance )

The diagnosis-derived signals (root cause, category) are SCALED by the diagnosis
confidence: when the diagnosis is uncertain, its relevance boosts count for less,
so a strong semantic match is not overridden by a low-confidence hypothesis; when
confidence is high, diagnosis relevance can outrank raw similarity. Weights are
constants (sum to 1.0 at full confidence), so ranking is fully deterministic and
reproducible. A future learned re-ranker plugs in as an alternative Ranker
implementation; nothing else changes.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.ally.rag.schemas import (
    KnowledgeChunk,
    RankingScore,
    RetrievalFilters,
    RetrievedKnowledge,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")
_QUANT = Decimal("0.000001")


def _clamp01(value: Decimal) -> Decimal:
    return max(_ZERO, min(_ONE, value))


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


class RankingWeights:
    """Relevance weights (sum to 1.0). Constants -> deterministic ranking."""

    def __init__(
        self,
        similarity: Decimal = Decimal("0.40"),
        root_cause: Decimal = Decimal("0.25"),
        category: Decimal = Decimal("0.15"),
        stage: Decimal = Decimal("0.10"),
        industry: Decimal = Decimal("0.10"),
    ):
        self.similarity = similarity
        self.root_cause = root_cause
        self.category = category
        self.stage = stage
        self.industry = industry
        total = similarity + root_cause + category + stage + industry
        if abs(total - _ONE) > Decimal("0.0001"):
            raise ValueError(f"Ranking weights must sum to 1.0, got {total}.")


class Ranker:
    def __init__(self, weights: RankingWeights | None = None):
        self.weights = weights or RankingWeights()

    def rank(
        self,
        chunks,
        filters: RetrievalFilters,
        *,
        confidence: Decimal | None,
    ) -> list[RetrievedKnowledge]:
        conf = _clamp01((confidence or _ZERO) / _HUNDRED)
        w = self.weights

        scored: list[tuple[Decimal, KnowledgeChunk, RankingScore]] = []
        for c in chunks:
            sim = _clamp01(c.similarity)
            stage_m = _ONE if (c.stage is not None and c.stage in filters.stages) else _ZERO
            ind_m = (
                _ONE
                if (c.industry is not None and filters.industry is not None and c.industry == filters.industry)
                else _ZERO
            )
            rc_rel = (
                _ONE
                if (set(c.root_cause_ids) & set(filters.root_cause_ids))
                else _ZERO
            )
            cat_rel = _ONE if (c.category is not None and c.category in filters.categories) else _ZERO

            # Diagnosis-derived relevance (root cause, category) is scaled by the
            # diagnosis confidence; similarity/stage/industry are not.
            total = _q(
                w.similarity * sim
                + w.stage * stage_m
                + w.industry * ind_m
                + conf * (w.root_cause * rc_rel + w.category * cat_rel)
            )
            score = RankingScore(
                similarity=sim,
                stage_match=stage_m,
                industry_match=ind_m,
                root_cause_relevance=rc_rel,
                category_relevance=cat_rel,
                confidence=conf,
                total=total,
            )
            scored.append((total, c, score))

        # Deterministic order: total desc, then similarity desc, then quality desc,
        # then chunk_id asc -- a total order, so ties never reorder between runs.
        scored.sort(key=lambda t: (-t[0], -t[1].similarity, -t[1].source_quality, t[1].chunk_id))

        return [
            RetrievedKnowledge(chunk=c, score=s, rank=i + 1)
            for i, (_total, c, s) in enumerate(scored)
        ]
