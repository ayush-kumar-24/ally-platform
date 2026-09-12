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

THREE FILTERS. All derive from the same dimension set -- see the `business_dna`
module docstring for the measurements behind the second and third:

    dimensions  the finest and most faithful test, via problems.dimension_code
    pillars     which SUBJECTS may be raised, via problems.pillar_id
    categories  what a question is ABOUT, via questions.category

Pillar alone is not enough because pillar membership does not mean what the
pillar's name means. Marketing Execution questions are filed under Market
Clarity, which Part 3 puts fully in scope at ideation -- so pillar scope on its
own would hand a founder with nothing built a run of questions about marketing
tooling and campaign attribution.

Dimension is the test the document actually specifies, and it is the only one
that can express Part 3's two dimension-level exclusions (Revenue Concentration
and Hiring Repeatability, withheld through Stage 0->1) -- both sit in pillars
that are fully in scope, so no pillar set and no category set can withhold them.
It applies only where `problems.dimension_code` is populated, which today is a
minority of the catalogue: the mapping is derivable for five categories and
needs a content pass for the rest (migration c3f7b28d5e91 and
scripts/backfill_problem_dimensions.py). An unmapped problem is admitted, not
dropped -- the coarser two tests still apply to it, and NULL means "not yet
known", never "not in scope".

A fourth filter lives elsewhere and is a different axis again: the repository
filters on `primary_stage_group`, which decides how a question is WORDED for
this founder. Scope decides what may be asked; stage group decides how it reads.

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
    pillars_for,
    withheld_categories_for,
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
    #: True everywhere, including ideation, which used to be the one exception.
    #: The case for excluding it was arithmetic: PILLAR_SCORE_FROM_ANSWERS drops
    #: an unanswered pillar and renormalises the rest to 100, and with only
    #: Founder Readiness (25) and Market Clarity (20) in scope, 45% of the model
    #: was being rescaled to 100 and labelled "Business Health Score" -- a
    #: verdict on a business that does not exist yet.
    #:
    #: Three things have changed and none of them leave that argument standing:
    #:
    #:   * Part 3 puts FOUR pillars at ideation, not two. Only Revenue Maturity
    #:     and Team & Leadership are out, and those are genuinely inapplicable
    #:     rather than merely unasked -- excluding them is the correct reading,
    #:     not a gap in one.
    #:   * The reader is told. `_business_dna` emits pillars_assessed,
    #:     pillars_total and assessed_weight_pct, and the narrator renders
    #:     "Across the four readiness pillars that apply at your stage" rather
    #:     than implying all six. It prints bands, never raw numbers.
    #:   * A pillar with too little evidence to support a band no longer gets
    #:     one at all (Settings.MIN_ANSWERS_PER_PILLAR_SCORE), so a thin session
    #:     narrows the score rather than inventing precision for it.
    #:
    #: Withholding it entirely was costing more than it protected: Part 1 of the
    #: document promises "which pillar is under the most strain right now, and
    #: why", and an ideation founder was getting no "Where you stand" section at
    #: all -- the report simply omitted it.
    #:
    #: Kept as a per-stage flag rather than deleted. It is the product switch for
    #: this decision, and no stage setting it False today is not a reason to make
    #: the decision unexpressible.
    emits_business_health: bool

    @cached_property
    def pillars(self) -> frozenset[int]:
        """Pillars with at least one live dimension. Filtered on."""
        return pillars_for(self.dimensions)

    @cached_property
    def withheld_categories(self) -> frozenset[str]:
        """Question categories this stage must not be asked about. Filtered on.

        Empty for every stage from Validation on. A deny-list rather than an
        allow-list, for the reason recorded on EXECUTION_CATEGORIES.
        """
        return withheld_categories_for(self.dimensions)

    @cached_property
    def excluded_dimensions(self) -> frozenset[str]:
        """Dimensions Part 3 withholds at this stage.

        Filtered on for questions whose problem carries a `dimension_code`, and
        carried regardless so the report can name what was deliberately not
        assessed rather than leaving it looking unanswered. Most of the
        catalogue is still unmapped -- see `business_dna.DIMENSION_BY_CATEGORY`.
        """
        return ALL_DIMENSION_CODES - self.dimensions

    @property
    def covers_all_pillars(self) -> bool:
        return self.pillars == ALL_PILLARS

    @property
    def withholds_nothing(self) -> bool:
        """True when no filter would remove anything, so all three can be
        skipped. Not the same as `covers_all_pillars`: a stage can reach every
        pillar and still withhold categories or dimensions within one."""
        return (
            self.covers_all_pillars
            and not self.withheld_categories
            and not self.excluded_dimensions
        )


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
    emits_business_health=True,
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
