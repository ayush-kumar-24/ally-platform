"""Whether a founder has sold anything yet, and what that means for questions.

A FIFTH AXIS, beside stage, context, industry and team size, and separate from
each for the same kind of reason they are separate from one another:

    stage     is this founder far enough along to have an answer?
    context   is this subject part of their situation at all?
    industry  was this question written for someone else's business?
    team      are there enough people here for the question to have a subject?
    revenue   has money changed hands yet?

Stage looks like it should cover this and does not. Validation, Prototype/MVP
and Early Traction share one question bank and one set of rules, so a founder
still testing whether anyone wants the idea is a valid candidate for "Have you
hit your sales targets for the last quarter?" -- the same question their
Early Traction neighbour gets, because the two are the same stage as far as the
bank is concerned.

WHERE THE ANSWER COMES FROM. Two sources, in order:

  * THE STAGE, for Ideation and Validation. Neither is asked for a revenue
    figure -- Ideation never was, Validation stopped when onboarding gained
    `minStageOrder` -- because neither can have one. That absence is not
    missing data: it is the answer, and reading it as unknown would leave the
    two stages the gate exists for ungated.
  * `founders.current_revenue` from Prototype/MVP on, where onboarding does
    ask. 'pre_revenue' is a real band a founder picks deliberately.

Everything else is UNKNOWN and gates nothing: a founder with no stage recorded,
a stage past Validation with the revenue question unanswered, a value the
column's CHECK would not recognise. Absence of a fact is never evidence for
withholding -- the same reading `team_scope` gives an unrecorded team size and
`_in_scope` gives an unmapped dimension.
"""

from __future__ import annotations

from typing import Any

from app.core.logger import logger

#: `founders.current_revenue`'s pre-revenue band. The only value of that column
#: that means "nothing sold yet"; every other band is money.
PRE_REVENUE = "pre_revenue"

#: The bands the column accepts. A value outside this is not evidence of
#: anything, so it reads as unknown rather than as pre-revenue.
REVENUE_BANDS: frozenset[str] = frozenset(
    {PRE_REVENUE, "under_1L", "1L_5L", "5L_25L", "25L_1Cr", "above_1Cr"}
)

#: Stages that cannot have revenue, so are never asked for a figure.
#: 1 Ideation, 2 Validation. Kept as orders rather than names because order is
#: what survives a re-seed of the stage table -- same reasoning as
#: `_STAGE_ORDER_TO_GROUP`.
PRE_REVENUE_STAGE_ORDERS: frozenset[int] = frozenset({1, 2})


def is_trading(founder: Any) -> bool | None:
    """True if money has changed hands, False if not, None if we cannot tell."""
    order = getattr(getattr(founder, "stage", None), "stage_order", None)
    if isinstance(order, int) and order in PRE_REVENUE_STAGE_ORDERS:
        return False

    band = getattr(founder, "current_revenue", None)
    if not isinstance(band, str):
        return None
    band = band.strip()
    if band not in REVENUE_BANDS:
        return None
    return band != PRE_REVENUE


def gate(candidates: list, founder: Any) -> list:
    """Drop the questions that need a sale this founder has not made.

    Degrades exactly like `team_scope.gate`: three ways to end up not gating --
    an unknown trading status, a question that needs nothing, or a gate that
    would empty the set -- and every one admits the question rather than
    withholding it.

    Never returns empty when it was given a non-empty set.
    """
    if not candidates:
        return candidates
    if is_trading(founder) is not False:
        return candidates                 # trading, or we cannot tell

    kept = [q for q in candidates if not getattr(q, "requires_trading", False)]

    if not kept:
        logger.warning(
            "Revenue gate matched no candidate question; leaving the set "
            "ungated rather than ending the diagnosis",
            extra={"stage": "revenue_scope", "candidates": len(candidates)},
        )
        return candidates

    if len(kept) != len(candidates):
        logger.info(
            "diagnosis gated on whether the founder is trading yet",
            extra={
                "stage": "revenue_scope",
                "withheld": len(candidates) - len(kept),
                "candidates": len(candidates),
            },
        )
    return kept
