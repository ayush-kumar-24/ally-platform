"""The Business DNA model: six pillars, twenty dimensions, and which of them
each stage may be diagnosed on.

SOURCE OF TRUTH. `GoXL Business DNA -- The Decoding Journey` Parts 2 and 3.
Everything in this module is a transcription of those two parts, and nothing
here is a judgement call that the document does not already make. That is the
point of pulling it out of `stage_scope.py`: the stage table used to be written
directly as pillar sets derived from a rule of our own ("what exists yet"),
which read plausibly and did not match Part 3 at any stage below Early Traction.
Stating the document first and deriving the pillar sets from it means the two
cannot drift again -- change the document, change the `STAGE_*_EXCLUDED` sets
below, and the pillar and category scope both follow.

WHY DIMENSIONS AND NOT JUST PILLARS. Part 3 does not scope by pillar. It scopes
by dimension, and three of its rules cannot be said in pillars at all:

    Stage 0      Pillars 1 and 6 apply for 2 of their 3 dimensions each,
                 and Pillar 4 for exactly one of its three.
    Stage 0->1   All 20 except Revenue Concentration and Hiring Repeatability.

A pillar set can express neither. So the document's dimension list is what this
module holds, and `pillars_for()` derives the coarser view from it.

WHAT IS ENFORCEABLE TODAY. `questions` has no dimension column -- a question's
pillar is reachable (question.problem_id -> problems.pillar_id) but its
dimension is not. So the dimension sets below drive two things that ARE
enforceable, and record one that is not:

  * PILLAR scope, derived by `pillars_for()`. Enforced in engine._in_scope.
  * CATEGORY scope, via `categories_for()`. Also enforced there, and it is not
    redundant with pillar scope -- see the next section.
  * The dimension exclusions themselves, exposed as `excluded_dimensions` on
    the scope so the report can say what was deliberately not assessed, and so
    that adding a `questions.dimension_code` column later is a filter change
    here rather than a redesign.

WHY CATEGORY SCOPE IS A SEPARATE AXIS. Because pillar membership does not mean
what the pillar's NAME means. Measured across the shipped question batches,
category maps onto pillar as a clean partition:

    Founder Psychology  -> 1     Product                        -> 4
    Idea & Validation   -> 2     Team & Leadership              -> 5
    Competitive Aware.  -> 2     Opportunity Evaluation         -> 6
    Marketing Execution -> 2     Business Planning              -> 6
    Sales Execution     -> 3     Scaling & Operational Maturity -> 6
    Sales & Revenue     -> 3     Go-To-Market                   -> 2 and 3
    Financial Mgmt      -> 3

Read the second column of that table against Part 2. Market Clarity's four
dimensions are Problem Definition, Customer Definition, Competitive Awareness
and Market Sizing Reality -- none of which is "do you have marketing tooling".
Yet 90 Marketing Execution questions sit under pillar 2, because their problems
(`No Dedicated Marketing Capability`, `No Marketing Tools or Performance
Tracking`) were filed there. Market Clarity is FULLY in scope at ideation under
Part 3. So widening ideation to the document's four pillars, on its own, would
newly admit marketing-execution questions to a founder with no product, no
channel and nothing to market -- the precise failure the scope rule exists to
prevent, arriving through the fix for it.

The category axis closes that. A pre-launch founder is asked about the clarity
of their market, not about the execution of marketing in it, and the two are
distinguishable by category even where the pillar cannot tell them apart.
"""

from dataclasses import dataclass

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

PILLAR_NAMES: dict[int, str] = {
    FOUNDER_READINESS: "Founder Readiness",
    MARKET_CLARITY: "Market Clarity",
    REVENUE_MATURITY: "Revenue Maturity",
    PRODUCT_AND_EXECUTION: "Product & Execution",
    TEAM_AND_LEADERSHIP: "Team & Leadership",
    STRATEGIC_CLARITY: "Strategic Clarity",
}


@dataclass(frozen=True)
class Dimension:
    """One of Part 2's twenty dimensions.

    `code` is ours -- the document names dimensions in prose, so a stable
    identifier had to be coined. It is the name lowercased and underscored,
    which keeps the two readable against each other.
    """

    code: str
    name: str
    pillar_id: int


# ---------------------------------------------------------------------------
# Part 2 -- The Six Pillars & Twenty Dimensions, in the document's own order.
# ---------------------------------------------------------------------------
DIMENSIONS: tuple[Dimension, ...] = (
    # -- Pillar 1, Founder Readiness --
    Dimension("skill_stage_fit", "Skill-Stage Fit", FOUNDER_READINESS),
    Dimension("time_allocation_reality", "Time Allocation Reality", FOUNDER_READINESS),
    Dimension("founder_dependency", "Founder Dependency / Bus Factor", FOUNDER_READINESS),
    # -- Pillar 2, Market Clarity --
    Dimension("problem_definition", "Problem Definition", MARKET_CLARITY),
    Dimension("customer_definition", "Customer Definition (ICP)", MARKET_CLARITY),
    Dimension("competitive_awareness", "Competitive Awareness", MARKET_CLARITY),
    Dimension("market_sizing_reality", "Market Sizing Reality", MARKET_CLARITY),
    # -- Pillar 3, Revenue Maturity --
    Dimension("demand_reality", "Demand Reality", REVENUE_MATURITY),
    Dimension("revenue_model_clarity", "Revenue Model Clarity", REVENUE_MATURITY),
    Dimension("revenue_concentration", "Revenue Concentration", REVENUE_MATURITY),
    Dimension("pricing_confidence", "Pricing Confidence", REVENUE_MATURITY),
    # -- Pillar 4, Product & Execution --
    Dimension("build_demand_alignment", "Build-Demand Alignment", PRODUCT_AND_EXECUTION),
    Dimension("execution_velocity", "Execution Velocity", PRODUCT_AND_EXECUTION),
    Dimension("reliability_real_world", "Reliability in the Real World", PRODUCT_AND_EXECUTION),
    # -- Pillar 5, Team & Leadership --
    Dimension("team_structure_role_clarity", "Team Structure & Role Clarity", TEAM_AND_LEADERSHIP),
    Dimension("decision_rights", "Decision Rights", TEAM_AND_LEADERSHIP),
    Dimension("hiring_repeatability", "Hiring Repeatability", TEAM_AND_LEADERSHIP),
    # -- Pillar 6, Strategic Clarity --
    Dimension("plan_to_vision_alignment", "Plan-to-Vision Alignment", STRATEGIC_CLARITY),
    Dimension("prioritization_discipline", "Prioritization Discipline", STRATEGIC_CLARITY),
    Dimension("institutional_memory", "Institutional Memory", STRATEGIC_CLARITY),
)

DIMENSION_BY_CODE: dict[str, Dimension] = {d.code: d for d in DIMENSIONS}
ALL_DIMENSION_CODES = frozenset(DIMENSION_BY_CODE)


def dimensions_in(pillar_id: int) -> frozenset[str]:
    return frozenset(d.code for d in DIMENSIONS if d.pillar_id == pillar_id)


# ---------------------------------------------------------------------------
# Part 3 -- The Business DNA Journey, By Stage.
#
# Stated as what each stage EXCLUDES rather than what it includes, because that
# is how the document states it ("all 20 dimensions become live except ...")
# and because a new dimension added to Part 2 should default to live rather
# than silently vanish from every stage.
# ---------------------------------------------------------------------------

#: Stage 0, Ideation. Part 3: "Pillar 2 (Market Clarity) fully applies; Pillars
#: 1 and 6 partially apply (2 of 3 dimensions each); plus Execution Velocity
#: from Pillar 4 -- 9 dimensions total. Everything else is not yet meaningful
#: to ask."
#:
#: WHICH 2 of 3, for pillars 1 and 6, is not stated in the prose -- it is
#: settled by Part 3's own Stage 0 example-question table, which lists
#: Skill-Stage Fit and Time Allocation Reality for pillar 1, and Plan-to-Vision
#: Alignment and Prioritization Discipline for pillar 6. The two it omits are
#: the two that need a running business: you cannot have a bus factor with no
#: bus, and there is no institutional memory before there is an institution.
STAGE_0_EXCLUDED = frozenset(
    {
        "founder_dependency",       # pillar 1, the third of three
        "institutional_memory",     # pillar 6, the third of three
        "build_demand_alignment",   # pillar 4, all but Execution Velocity
        "reliability_real_world",   # pillar 4
    }
    | dimensions_in(REVENUE_MATURITY)
    | dimensions_in(TEAM_AND_LEADERSHIP)
)

#: Stage 0->1: Validation, Prototype, Early Traction. Part 3: "All 20
#: dimensions become live except Revenue Concentration and Hiring
#: Repeatability, which need an actual revenue base and multiple hires
#: respectively to produce a real signal."
#:
#: Note this is ONE band in the document, not three. An earlier scope table
#: split it -- Validation on 3 pillars, Prototype/MVP on 4, Early Traction on 6
#: -- which withheld Team & Leadership and Strategic Clarity from two thirds of
#: the band the document says is fully live.
STAGE_0_TO_1_EXCLUDED = frozenset({"revenue_concentration", "hiring_repeatability"})

#: Stage 1->10+: Growth through Exit. Part 3: "All 20 dimensions apply."
STAGE_1_TO_10_PLUS_EXCLUDED: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# The category axis. See the module docstring for why this is not redundant
# with pillar scope.
# ---------------------------------------------------------------------------

#: `questions.category` -> the pillar its questions score. Measured across the
#: shipped question batches, where the mapping is a clean partition apart from
#: Go-To-Market, which straddles Market Clarity and Revenue Maturity.
#:
#: Advisory, not authoritative: the pillar a question actually scores is always
#: read from problems.pillar_id. This table exists to say what a category IS
#: ABOUT, which is a different question and the one the stage rule needs.
PILLAR_BY_CATEGORY: dict[str, int] = {
    "Founder Psychology": FOUNDER_READINESS,
    "Idea & Validation": MARKET_CLARITY,
    "Competitive Awareness": MARKET_CLARITY,
    "Marketing Execution": MARKET_CLARITY,
    "Go-To-Market": MARKET_CLARITY,
    "Sales Execution": REVENUE_MATURITY,
    "Sales & Revenue": REVENUE_MATURITY,
    "Financial Management": REVENUE_MATURITY,
    "Fundraising": REVENUE_MATURITY,
    "Product": PRODUCT_AND_EXECUTION,
    "Team & Leadership": TEAM_AND_LEADERSHIP,
    "Opportunity Evaluation": STRATEGIC_CLARITY,
    "Business Planning": STRATEGIC_CLARITY,
    "Scaling & Operational Maturity": STRATEGIC_CLARITY,
}

#: Categories a founder with no product, no channel, no customer and no team
#: has nothing to say about -- the ones that interrogate the EXECUTION of a
#: going concern rather than the clarity of an idea.
#:
#: Every one of these presupposes something an ideation founder does not have:
#: a channel to market through, a pipeline to run, money moving, or people to
#: lead. Part 3 puts it as "asking a solo, pre-launch founder about hiring
#: repeatability or revenue concentration produces noise, not signal" -- the
#: same reasoning, applied to the whole bank rather than to the two dimensions
#: it happens to name.
#:
#: This is an ALLOW-list in effect (see `categories_for`), not a deny-list, and
#: deliberately so: ideation is where the noise costs most and where the bank
#: is smallest and best understood, so a category seeded later should have to
#: be admitted on purpose rather than arrive by default. Every other stage
#: fails open, because Part 3 puts all six pillars in scope from Validation on
#: and there is nothing left to withhold.
IDEATION_CATEGORIES = frozenset(
    {
        "Founder Psychology",       # the founder exists before the business does
        "Idea & Validation",
        "Competitive Awareness",
        "Opportunity Evaluation",   # Prioritization Discipline, live at Stage 0
        "Business Planning",        # Plan-to-Vision Alignment, live at Stage 0
        "Product",                  # Execution Velocity, live at Stage 0
    }
)


def pillars_for(dimension_codes: frozenset[str]) -> frozenset[int]:
    """The pillars a dimension set touches -- the coarse view of Part 3.

    A pillar is in scope when AT LEAST ONE of its dimensions is live, which is
    the only reading that survives Part 3's partial pillars: Stage 0 has one of
    Product & Execution's three dimensions, and dropping the whole pillar over
    the other two is what the previous scope table did.
    """
    return frozenset(
        DIMENSION_BY_CODE[code].pillar_id
        for code in dimension_codes
        if code in DIMENSION_BY_CODE
    )


def categories_for(dimension_codes: frozenset[str]) -> frozenset[str] | None:
    """Question categories in scope for this dimension set, or None for "all".

    None rather than the full set so the caller can skip the filter entirely
    when nothing is being withheld -- and so a category seeded after this was
    written is admitted at every stage that withholds nothing, rather than
    silently dropped everywhere.
    """
    if dimension_codes >= ALL_DIMENSION_CODES - STAGE_0_TO_1_EXCLUDED:
        # Validation onward: Part 3 puts every pillar in scope, so there is no
        # category to withhold. Fail open.
        return None
    return IDEATION_CATEGORIES
