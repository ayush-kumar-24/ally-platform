"""Retrieval Filter Engine -- builds deterministic filters from AllyContext.

This runs BEFORE any vector search. It reads ONLY the immutable AllyContext (M1)
and produces a RetrievalFilters describing the founder's situation, so the
repository can narrow the search space to diagnosis-relevant knowledge instead of
searching everything (which is known to give poor results). Pure and
deterministic: same context + same params -> same filters, no DB, no randomness.
"""

from __future__ import annotations

from decimal import Decimal

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.rag.schemas import RetrievalFilters

_ZERO = Decimal("0")


def _ordered_unique(values) -> tuple:
    """Order-preserving de-duplication (deterministic)."""
    return tuple(dict.fromkeys(v for v in values if v is not None))


def build_filters(
    context: AllyContext,
    *,
    top_k: int = 5,
    min_similarity: Decimal = _ZERO,
    intent: str | None = None,
    allow_sales_collateral: bool = False,
) -> RetrievalFilters:
    founder = context.founder

    # Root-cause scope: prefer the top findings; fall back to all detected causes.
    top_ids = _ordered_unique(
        rc.root_cause_id for rc in context.root_causes if rc.is_top_finding
    )
    all_ids = _ordered_unique(rc.root_cause_id for rc in context.root_causes)
    root_cause_ids = top_ids or all_ids

    # Category scope: the categories the detected root causes belong to.
    categories = _ordered_unique(rc.category for rc in context.root_causes)

    band = context.business_health.band if context.business_health is not None else None

    return RetrievalFilters(
        # rag_documents.stage_relevance is tagged with the diagnosis question
        # bank's stage-GROUP vocabulary ("Stage 0->1", "Stage 1->10+", ...),
        # not individual stage names ("Early Traction", "Validation", ...) --
        # using stage_name here matched nothing for any stage-tagged document,
        # silently and permanently. See FounderProfileContext.stage_groups.
        stages=_ordered_unique(founder.stage_groups),
        industry=founder.industry,
        root_cause_ids=root_cause_ids,
        categories=categories,
        business_health_band=band,
        distress_mode=context.is_distress,
        min_similarity=min_similarity,
        top_k=max(0, top_k),
        intent=intent,
        allow_sales_collateral=allow_sales_collateral,
    )
