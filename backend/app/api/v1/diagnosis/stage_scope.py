"""Which readiness pillars a founder's stage is allowed to be diagnosed on.

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

So scope is a product rule, applied before ranking: a question whose pillar is
out of scope for the founder's stage is never a candidate.

WHAT DECIDES SCOPE. Not the stage label on its own -- what actually exists yet:

    a paying or using customer   -> Revenue Maturity means something
    a product used by a stranger -> Product & Execution means something
    a person who is not the founder -> Team & Leadership means something

Ideation has none of the three, so it is diagnosed on the two layers that do
exist: the founder themselves, and whether the idea has been validated.

RELATIONSHIP TO THE THREE STAGE GROUPS. `questions.primary_stage_group` buckets
the bank into three, which is about question CONTENT -- how a question is worded
for where the founder is. This is about SUBJECT -- which pillars may be asked
about at all. They are different axes and both apply: `resolve_stage_groups`
picks the wording, this picks the subject. Eight stages are differentiated by
scope and budget, not by re-tagging 3,340 questions into eight buckets.

WHERE THE BUDGET LIVES. Not here. `founder_stages.question_budget` holds it, so
the completion ceiling and the confidence coverage denominator read one number
from one place (see `Settings.question_budget`). Seeded by migration
`8f3a1c92d7b4`; the intended values are recorded there.
"""

from dataclasses import dataclass

from app.core.logger import logger

# Pillar ids as seeded in `readiness_pillars`. Named because a bare {1, 2} in a
# scope table is unreadable and a wrong id is invisible in review.
FOUNDER_READINESS = 1
MARKET_CLARITY = 2
REVENUE_MATURITY = 3
PRODUCT_AND_EXECUTION = 4
TEAM_AND_LEADERSHIP = 5
STRATEGIC_CLARITY = 6

ALL_PILLARS = frozenset(
    {
        FOUNDER_READINESS,
        MARKET_CLARITY,
        REVENUE_MATURITY,
        PRODUCT_AND_EXECUTION,
        TEAM_AND_LEADERSHIP,
        STRATEGIC_CLARITY,
    }
)


@dataclass(frozen=True)
class StageScope:
    """What one stage may be diagnosed on, and what it may report."""

    label: str
    pillars: frozenset[int]

    #: Whether a Business Health Score may be published for this stage.
    #:
    #: False for ideation, and the reason is arithmetic rather than editorial.
    #: PILLAR_SCORE_FROM_ANSWERS excludes an unanswered pillar and renormalises
    #: the remaining weights to sum to 100. With only Founder Readiness (25) and
    #: Market Clarity (20) in scope, 45% of the model would be renormalised up to
    #: 100 and shown to the founder as their "Business Health Score" -- a number
    #: that reads as a verdict on a business that does not exist yet. An ideation
    #: founder gets the Founder DNA Snapshot and an Idea Validation read instead.
    emits_business_health: bool

    @property
    def covers_all_pillars(self) -> bool:
        return self.pillars == ALL_PILLARS


#: Scope by `founder_stages.stage_order` (1..8), not stage_id. Order is the
#: meaningful axis -- it is what `_STAGE_ORDER_TO_GROUP` reads and what survives
#: a re-seed of the stage table.
_IDEATION = StageScope(
    label="Ideation",
    # Founder DNA plus Idea Validation. Market Clarity is where the bank keeps
    # Idea & Validation, Target Customer & ICP and Competitive Awareness.
    pillars=frozenset({FOUNDER_READINESS, MARKET_CLARITY}),
    emits_business_health=False,
)

_VALIDATION = StageScope(
    label="Validation",
    # Something now exists to test, so how it is built becomes fair to ask about.
    # Revenue stays out: testing demand is not yet earning from it.
    pillars=frozenset({FOUNDER_READINESS, MARKET_CLARITY, PRODUCT_AND_EXECUTION}),
    emits_business_health=True,
)

_PROTOTYPE_MVP = StageScope(
    label="Prototype / MVP",
    # Revenue joins as INTENT -- how the founder plans to charge and why. The
    # dimensions needing an actual revenue base (Revenue Concentration) have no
    # Stage 0->1 content in the bank, so they cannot be asked here anyway.
    pillars=frozenset(
        {FOUNDER_READINESS, MARKET_CLARITY, PRODUCT_AND_EXECUTION, REVENUE_MATURITY}
    ),
    emits_business_health=True,
)

_FULL = StageScope(label="Full business", pillars=ALL_PILLARS, emits_business_health=True)

SCOPE_BY_STAGE_ORDER: dict[int, StageScope] = {
    1: _IDEATION,
    2: _VALIDATION,
    3: _PROTOTYPE_MVP,
    # From Early Traction on there is a product, customers and usually a team,
    # so all six pillars carry real signal. Stages 4-8 differ by question budget
    # and by how the bank words a question, not by which pillars are in scope.
    4: _FULL,
    5: _FULL,
    6: _FULL,
    7: _FULL,
    8: _FULL,
}


def scope_for(stage) -> StageScope | None:
    """Scope for a `FounderStage` row, or None when it cannot be determined.

    None means "do not scope" -- every pillar stays eligible. That is the same
    fail-open convention `stage_groups_for` uses for an unknown stage: onboarding
    may be incomplete, and narrowing an unknown founder to two pillars would
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
