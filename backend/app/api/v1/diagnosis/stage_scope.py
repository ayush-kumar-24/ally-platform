"""What a founder's stage may be diagnosed on.

The diagnosis used to ask every founder about all six pillars. The pillar
round-robin in `engine.py` guarantees it: giving each pillar its turn is what
stopped Founder Psychology draining the whole budget, but it also walks a
pre-launch solo founder through Revenue Maturity and Team & Leadership. Measured
on the live Stage 0 bank, 20 of an ideation founder's 30 questions landed
outside Founder DNA and Idea Validation, and 10 of those asked someone with no
revenue and no team about revenue models and team structure.

Those answers are not weak signal, they are absent signal. The founder has
nothing to report, the classifier reads the shrug as risk, and a pillar that
should not have been assessed at all ends up scored. `GoXL_Business_DNA` puts it
directly: asking a solo, pre-launch founder about hiring repeatability or
revenue concentration "produces noise, not signal".

So scope is a product rule, applied before ranking: a question out of scope for
the founder's stage is never a candidate.

WHERE THE RULE COMES FROM. `business_dna.py`, which transcribes the document's
Part 2 and Part 3. This module is now only the stage_order -> dimension-set
lookup plus the two derived views the engine filters on. It used to hold the
rule itself, written as pillar sets derived from a premise of our own -- not the
stage label but "what actually exists yet": a paying customer, a product a
stranger uses, a person who is not the founder. That premise is reasonable and
it is not the document's. It disagreed with Part 3 at every stage below Early
Traction, most sharply at ideation, where it withheld Product & Execution and
Strategic Clarity entirely -- 98 of the 245 questions in the shipped Stage 0
bank, and with them Execution Velocity, Plan-to-Vision Alignment and
Prioritization Discipline, three of the nine dimensions Part 3 puts at Stage 0.

TWO FILTERS, NOT ONE. Both derive from the same dimension set, and both are
needed -- see the `business_dna` module docstring for the measurement behind the
second:

    pillars     which SUBJECTS may be raised, via problems.pillar_id
    categories  what a question is ABOUT, via questions.category

Pillar alone is not enough because pillar membership does not mean what the
pillar's name means. Marketing Execution questions are filed under Market
Clarity, which Part 3 puts fully in scope at ideation -- so pillar scope on its
own would hand a founder with nothing built a run of questions about marketing
tooling and campaign attribution.

A third filter lives elsewhere and is a different axis again: the repository
filters on `primary_stage_group`, which decides how a question is WORDED for
this founder. Scope decides what may be asked; stage group decides how it reads.

WHAT IS NOT ENFORCEABLE YET. Part 3's two dimension-level exclusions -- Revenue
Concentration and Hiring Repeatability, withheld through Stage 0->1 -- cannot be
applied to candidates, because `questions` carries no dimension column. They are
recorded on the scope as `excluded_dimensions` so the report can state what was
deliberately not assessed, and so that adding that column later is a filter
change rather than a redesign. Everything Part 3 states at pillar or category
granularity IS enforced.

WHERE THE BUDGET LIVES. Not here. `founder_stages.question_budget` holds it, so
the completion ceiling and the confidence coverage denominator read one number
from one place (see `Settings.question_budget`). Seeded by migration
`8f3a1c92d7b4`; the intended values are recorded there.
"""

from dataclasses import dataclass
from functools import cached_property

from app.api.v1.diagnosis.business_dna import (
    ALL_DIMENSION_CODES,
    ALL_PILLARS,
    FOUNDER_READINESS,
    MARKET_CLARITY,
    PRODUCT_AND_EXECUTION,
    REVENUE_MATURITY,
    STAGE_0_EXCLUDED,
    STAGE_0_TO_1_EXCLUDED,
    STAGE_1_TO_10_PLUS_EXCLUDED,
    STRATEGIC_CLARITY,
    TEAM_AND_LEADERSHIP,
    categories_for,
    pillars_for,
)
from app.core.logger import logger

# Re-exported so callers that only care about scope do not need to know the
# model module exists. `business_dna` is where they are defined.
__all__ = [
    "ALL_PILLARS",
    "FOUNDER_READINESS",
    "MARKET_CLARITY",
    "PRODUCT_AND_EXECUTION",
    "REVENUE_MATURITY",
    "SCOPE_BY_STAGE_ORDER",
    "STRATEGIC_CLARITY",
    "TEAM_AND_LEADERSHIP",
    "StageScope",
    "resolve_scope",
    "scope_for",
]


@dataclass(frozen=True)
class StageScope:
    """What one stage may be diagnosed on, and what it may report."""

    label: str

    #: The Part 3 dimension set for this stage. The other two views derive from
    #: it, so there is one statement of the rule and not three that can drift.
    dimensions: frozenset[str]

    #: Whether a Business Health Score may be published for this stage.
    #:
    #: False for ideation. The original reason was arithmetic:
    #: PILLAR_SCORE_FROM_ANSWERS excludes an unanswered pillar and renormalises
    #: the remaining weights to sum to 100, and with only Founder Readiness (25)
    #: and Market Clarity (20) in scope, 45% of the model would be renormalised
    #: up to 100 and shown to the founder as their "Business Health Score" -- a
    #: number that reads as a verdict on a business that does not exist yet.
    #:
    #: That argument is weaker now. Part 3 puts four of the six pillars at
    #: ideation, not two, so the renormalised share is much larger. The flag is
    #: deliberately left as it was by the change that widened the scope: turning
    #: it on would newly publish a headline score to every ideation founder,
    #: which is a product decision and not a consequence of fixing the scope
    #: table. An ideation founder still gets the Founder DNA Snapshot and an
    #: Idea Validation read. Revisit with the pillar weights in hand.
    emits_business_health: bool

    @cached_property
    def pillars(self) -> frozenset[int]:
        """Pillars with at least one live dimension. Filtered on."""
        return pillars_for(self.dimensions)

    @cached_property
    def categories(self) -> frozenset[str] | None:
        """Question categories in scope, or None when nothing is withheld."""
        return categories_for(self.dimensions)

    @cached_property
    def excluded_dimensions(self) -> frozenset[str]:
        """Dimensions Part 3 withholds at this stage.

        Not filtered on -- `questions` has no dimension column. Carried so the
        report can name what was deliberately not assessed rather than leaving
        it looking unanswered.
        """
        return ALL_DIMENSION_CODES - self.dimensions

    @property
    def covers_all_pillars(self) -> bool:
        return self.pillars == ALL_PILLARS

    @property
    def withholds_nothing(self) -> bool:
        """True when neither filter would remove anything, so both can be
        skipped. Not the same as `covers_all_pillars`: a stage can reach every
        pillar and still withhold categories within one of them."""
        return self.covers_all_pillars and self.categories is None


#: Scope by `founder_stages.stage_order` (1..8), not stage_id. Order is the
#: meaningful axis -- it is what `_STAGE_ORDER_TO_GROUP` reads and what survives
#: a re-seed of the stage table.
#:
#: The three bands are Part 3's three, and the stage_order boundaries are the
#: ones `_STAGE_ORDER_TO_GROUP` in engine.py already uses for question wording,
#: so a founder is scoped and worded against the same band.
_IDEATION = StageScope(
    label="Ideation",
    dimensions=ALL_DIMENSION_CODES - STAGE_0_EXCLUDED,
    emits_business_health=False,
)

_EARLY = StageScope(
    label="Validation / Prototype / Early Traction",
    dimensions=ALL_DIMENSION_CODES - STAGE_0_TO_1_EXCLUDED,
    emits_business_health=True,
)

_FULL = StageScope(
    label="Growth through Exit",
    dimensions=ALL_DIMENSION_CODES - STAGE_1_TO_10_PLUS_EXCLUDED,
    emits_business_health=True,
)

SCOPE_BY_STAGE_ORDER: dict[int, StageScope] = {
    # Stage 0 -- Ideation.
    1: _IDEATION,
    # Stage 0->1 -- Validation, Prototype/MVP, Early Traction. Part 3 treats
    # these as ONE band with one dimension set; splitting them is what withheld
    # Team & Leadership and Strategic Clarity from Validation and Prototype
    # founders the document says are fully live on both.
    2: _EARLY,
    3: _EARLY,
    4: _EARLY,
    # Stage 1->10+ -- Growth, Expansion, Maturity, Exit. These differ from each
    # other by question budget and by how the bank words a question, not by
    # which dimensions are in scope.
    5: _FULL,
    6: _FULL,
    7: _FULL,
    8: _FULL,
}


def scope_for(stage) -> StageScope | None:
    """Scope for a `FounderStage` row, or None when it cannot be determined.

    None means "do not scope" -- every pillar and category stays eligible. That
    is the same fail-open convention `stage_groups_for` uses for an unknown
    stage: onboarding may be incomplete, and narrowing an unknown founder would
    silently under-diagnose them. Over-asking is recoverable; a pillar that was
    never asked about is missing from the report with nothing to show it.
    """
    order = getattr(stage, "stage_order", None)
    if order is None:
        return None
    scope = SCOPE_BY_STAGE_ORDER.get(order)
    if scope is None:
        logger.warning(
            "No diagnosis scope defined for this stage order; leaving every "
            "pillar in scope",
            extra={"stage_order": order},
        )
    return scope


def resolve_scope(founder) -> StageScope | None:
    """Scope for a founder, via their loaded `.stage` relationship."""
    return scope_for(getattr(founder, "stage", None))
