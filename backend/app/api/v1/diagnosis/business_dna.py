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


def dimension_names(codes) -> tuple[str, ...]:
    """Part 2's own names for these dimensions, in the document's order.

    Ordered by DIMENSIONS rather than by the caller's set so a pillar's
    dimensions always read in the same sequence, whatever order they arrived in
    -- these names reach the founder in a report line, and a list that reshuffles
    between two runs of the same report looks like the finding changed.
    """
    wanted = set(codes)
    return tuple(d.name for d in DIMENSIONS if d.code in wanted)


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
#: Measured over both snapshots taken from the live database -- the shipped
#: question batches and scripts/calibration/bank_stage0.json. Every problem in
#: those carries exactly one category, so problem -> category -> pillar is
#: single-valued; Go-To-Market is the one category whose problems straddle two
#: pillars (104 under Market Clarity, 12 under Revenue Maturity) and is recorded
#: at its majority.
PILLAR_BY_CATEGORY: dict[str, int] = {
    "Founder Psychology": FOUNDER_READINESS,
    "Idea & Validation": MARKET_CLARITY,
    "Competitive Awareness": MARKET_CLARITY,
    "Target Customer & ICP": MARKET_CLARITY,
    "Marketing Execution": MARKET_CLARITY,
    "Go-To-Market": MARKET_CLARITY,
    "Sales Execution": REVENUE_MATURITY,
    "Sales & Revenue": REVENUE_MATURITY,
    "Business Model Design": REVENUE_MATURITY,
    "Financial Management": REVENUE_MATURITY,
    "Fundraising": REVENUE_MATURITY,
    "Product": PRODUCT_AND_EXECUTION,
    "Operations & Systems": PRODUCT_AND_EXECUTION,
    "Team & Leadership": TEAM_AND_LEADERSHIP,
    "Opportunity Evaluation": STRATEGIC_CLARITY,
    "Business Planning": STRATEGIC_CLARITY,
    "Risk Identification": STRATEGIC_CLARITY,
    "Scaling & Operational Maturity": STRATEGIC_CLARITY,
}

#: Categories a founder with no product, no channel, no customer and no team
#: has nothing to say about -- the ones that interrogate the EXECUTION of a
#: going concern rather than the clarity of an idea.
#:
#: Every one presupposes something an ideation founder does not have: a channel
#: to market through, a pipeline to run, money moving, or people to lead. Part 3
#: puts it as "asking a solo, pre-launch founder about hiring repeatability or
#: revenue concentration produces noise, not signal" -- the same reasoning,
#: applied to the whole bank rather than to the two dimensions it names.
#:
#: A DENY-list, and the first cut of this was an allow-list, which was a real
#: bug. An allow-list has to enumerate every category that exists, and the
#: shipped question batches are not the whole bank: measured against the live
#: Stage 0 snapshot in scripts/calibration/bank_stage0.json, the allow-list
#: silently withheld 36 of its 472 questions, among them all 25 tagged
#: `Target Customer & ICP` -- which is Part 2's Customer Definition (ICP)
#: dimension, one of the nine Part 3 puts AT ideation. Denying what is known to
#: presuppose a business fails the safe way round: a category nobody listed here
#: is still filtered by pillar, and by dimension where one is recorded.
#:
#: Only ideation withholds anything. Part 3 puts all six pillars in scope from
#: Validation on, so there is nothing left to withhold after that.
EXECUTION_CATEGORIES = frozenset(
    {
        "Marketing Execution",            # pillar 2, and so NOT caught by pillar scope
        "Go-To-Market",                   # pillar 2, same
        "Scaling & Operational Maturity",  # pillar 6, same
        # The rest sit in pillars ideation already excludes. Listed anyway so
        # the rule reads as a rule rather than as a coincidence of pillar ids.
        "Sales Execution",
        "Sales & Revenue",
        "Financial Management",
        "Fundraising",
        "Team & Leadership",
    }
)


#: `questions.category` -> the Part 2 dimension its questions assess, for the
#: categories where that is a 1:1 fact rather than a judgement call.
#:
#: This is the backfill rule for `problems.dimension_code` (migration
#: c3f7b28d5e91) and the only part of the mapping derivable without reading the
#: live `problems` table. Each entry was checked against actual question text in
#: the shipped batches, not inferred from the category name:
#:
#:   Business Planning       "What's the biggest gap between where you want this
#:                            to go and what you're actually spending time on?"
#:   Opportunity Evaluation  "Are all opportunities right now being treated as
#:                            equally urgent, or is there a real system for
#:                            ranking them?"
#:   Competitive Awareness   "When did you last deliberately go looking for
#:                            competitors, rather than just noticing one by
#:                            accident?"
#:
#: INVARIANT, asserted below and in the migration: the dimension's pillar equals
#: the pillar the category's problems already carry. A mapping that moved a
#: question between pillars would silently rescore it.
DIMENSION_BY_CATEGORY: dict[str, str] = {
    "Target Customer & ICP": "customer_definition",
    "Competitive Awareness": "competitive_awareness",
    "Business Model Design": "revenue_model_clarity",
    "Business Planning": "plan_to_vision_alignment",
    "Opportunity Evaluation": "prioritization_discipline",
}

#: Categories deliberately NOT in the map above, and why. Kept as data so the
#: gap is inspectable rather than being the absence of something.
#:
#: AMBIGUOUS -- the category spans several of its pillar's dimensions, so any
#: single assignment would be fake precision. Sampled question text for each:
#:
#:   Founder Psychology  "If you had one extra hour today, would it actually go
#:                        to this idea?"            -> Time Allocation Reality
#:                       "How often do you catch yourself thinking it would just
#:                        be faster if I did this myself?" -> Founder Dependency
#:   Product             reliability metrics / shipping speed / bug ownership
#:                       -> all three of pillar 4's dimensions
#:   Team & Leadership   letting someone go / decision documentation / feedback
#:   Idea & Validation   Problem Definition and Market Sizing Reality both
#:   Sales & Revenue     conversation craft, which is none of pillar 3's four
#:
#: NO DIMENSION -- the doc's twenty do not cover this part of the bank at all.
#: Part 2 is a diagnostic lens over six pillars; the question bank is an
#: operational catalogue with families (marketing, sales and finance execution,
#: fundraising) that the lens simply does not name. These stay NULL permanently
#: unless Part 2 grows, and NULL is the honest value for them.
#:
#: MISFILED -- `Scaling & Operational Maturity` reads as Execution Velocity
#: ("has your team gotten measurably faster at shipping, or has speed actually
#: declined?") but its problems carry pillar 6, and Execution Velocity is
#: pillar 4. Assigning it would break the invariant above, so it is left for the
#: content pass to resolve along with the pillar id.
CATEGORIES_WITHOUT_A_DIMENSION: dict[str, str] = {
    "Founder Psychology": "ambiguous",
    "Idea & Validation": "ambiguous",
    "Product": "ambiguous",
    "Team & Leadership": "ambiguous",
    "Sales & Revenue": "ambiguous",
    "Operations & Systems": "ambiguous",
    "Risk Identification": "ambiguous",
    "Marketing Execution": "no dimension",
    "Go-To-Market": "no dimension",
    "Sales Execution": "no dimension",
    "Financial Management": "no dimension",
    "Fundraising": "no dimension",
    "Scaling & Operational Maturity": "misfiled pillar",
}


def _assert_category_mapping_keeps_its_pillar() -> None:
    """The invariant in DIMENSION_BY_CATEGORY's docstring, checked at import.

    Cheap (five entries) and it fails at start-up rather than producing a
    quietly rescored pillar in a founder's report.
    """
    for category, dimension_code in DIMENSION_BY_CATEGORY.items():
        expected = PILLAR_BY_CATEGORY.get(category)
        actual = DIMENSION_BY_CODE[dimension_code].pillar_id
        if expected is not None and expected != actual:
            raise AssertionError(
                f"{category!r} carries pillar {expected} but maps to "
                f"{dimension_code!r}, which is pillar {actual}"
            )


_assert_category_mapping_keeps_its_pillar()


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


def withheld_categories_for(dimension_codes: frozenset[str]) -> frozenset[str]:
    """Question categories this stage must not be asked about.

    Empty when nothing is withheld, which is every stage from Validation on:
    Part 3 puts all six pillars in scope there, so there is nothing left to
    hold back. Only ideation withholds, and it withholds the execution
    families -- see EXECUTION_CATEGORIES for why this is a deny-list.
    """
    if dimension_codes >= ALL_DIMENSION_CODES - STAGE_0_TO_1_EXCLUDED:
        return frozenset()
    return EXECUTION_CATEGORIES
