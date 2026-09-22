"""A pillar's name must not overstate what was assessed.

Business DNA Part 3 scopes several pillars PARTIALLY. At ideation, Product &
Execution is one of its three dimensions (Execution Velocity), and Founder
Readiness and Strategic Clarity are two of three each. Through Stage 0->1,
Revenue Maturity is three of four and Team & Leadership two of three, because
Part 3 withholds Revenue Concentration and Hiring Repeatability there.

Printing the bare pillar name over those readings claims more than was done.
"Product & Execution — Needs Attention" tells a pre-launch founder their product
was assessed; what was assessed was how fast they move.

Coverage is a property of the STAGE, not of the session: it says what the
assessment covers, which is identical for every founder at that stage. Which
dimensions a given session actually reached would need `problems.dimension_code`,
still mostly NULL.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.business_dna import dimension_names, dimensions_in
from app.api.v1.diagnosis.stage_scope import (
    FOUNDER_READINESS,
    MARKET_CLARITY,
    PRODUCT_AND_EXECUTION,
    REVENUE_MATURITY,
    SCOPE_BY_STAGE_ORDER,
    STRATEGIC_CLARITY,
    TEAM_AND_LEADERSHIP,
)
from app.api.v1.reports.document import (_coverage_note, _pillar_verdicts,
                                          _standing)
from app.api.v1.reports.narrator import TemplateNarrator, _pillar_label
from app.models.enums import ScoreLabel

IDEATION, EARLY, FULL = 1, 2, 5
TONE = SimpleNamespace(persona=None)


# --- the scope knows what it covers ----------------------------------------

def test_ideation_covers_one_of_three_product_dimensions():
    names, total = SCOPE_BY_STAGE_ORDER[IDEATION].coverage_of(PRODUCT_AND_EXECUTION)
    assert names == ("Execution Velocity",)
    assert total == 3


def test_ideation_covers_market_clarity_in_full():
    scope = SCOPE_BY_STAGE_ORDER[IDEATION]
    names, total = scope.coverage_of(MARKET_CLARITY)

    assert len(names) == total == 4
    assert scope.covers_all_of(MARKET_CLARITY)


@pytest.mark.parametrize("pillar", [FOUNDER_READINESS, STRATEGIC_CLARITY])
def test_ideation_covers_two_of_three(pillar):
    names, total = SCOPE_BY_STAGE_ORDER[IDEATION].coverage_of(pillar)
    assert (len(names), total) == (2, 3)


def test_a_pillar_out_of_scope_reports_none_of_its_dimensions():
    """Not an error -- "none of its four" is the honest answer for a pillar the
    stage never assessed."""
    names, total = SCOPE_BY_STAGE_ORDER[IDEATION].coverage_of(REVENUE_MATURITY)
    assert names == ()
    assert total == 4


def test_the_early_band_shows_part_3s_two_exclusions():
    """The dimension-level rules Part 3 states outright, surfacing in the label
    rather than only in a comment about what could not be enforced."""
    scope = SCOPE_BY_STAGE_ORDER[EARLY]

    assert "Revenue Concentration" not in scope.coverage_of(REVENUE_MATURITY)[0]
    assert "Hiring Repeatability" not in scope.coverage_of(TEAM_AND_LEADERSHIP)[0]
    assert not scope.covers_all_of(REVENUE_MATURITY)
    assert not scope.covers_all_of(TEAM_AND_LEADERSHIP)


@pytest.mark.parametrize("pillar", sorted({FOUNDER_READINESS, MARKET_CLARITY,
                                           REVENUE_MATURITY, PRODUCT_AND_EXECUTION,
                                           TEAM_AND_LEADERSHIP, STRATEGIC_CLARITY}))
def test_growth_covers_every_pillar_in_full(pillar):
    assert SCOPE_BY_STAGE_ORDER[FULL].covers_all_of(pillar)


def test_dimension_names_come_out_in_the_documents_order():
    """These reach the founder in a report line, so the order must not depend on
    set iteration -- the same report run twice must read the same."""
    codes = dimensions_in(MARKET_CLARITY)
    assert dimension_names(codes) == dimension_names(sorted(codes, reverse=True))
    assert dimension_names(codes)[0] == "Problem Definition"


# --- the label --------------------------------------------------------------

def _p(name, covered, total):
    return {"pillar_name": name, "dimensions_in_scope": covered, "dimensions_total": total}


def test_a_fully_covered_pillar_gets_no_qualifier():
    assert _pillar_label(_p("Market Clarity", ["a", "b", "c", "d"], 4)) == "Market Clarity"


def test_one_dimension_reads_as_only_that_one():
    label = _pillar_label(_p("Product & Execution", ["Execution Velocity"], 3))
    assert label == "Product & Execution (Execution Velocity only)"


def test_two_dimensions_are_joined_with_and():
    label = _pillar_label(
        _p("Strategic Clarity", ["Plan-to-Vision Alignment", "Prioritization Discipline"], 3)
    )
    assert label == (
        "Strategic Clarity (Plan-to-Vision Alignment and Prioritization Discipline only)"
    )


def test_three_of_four_reads_as_a_list():
    label = _pillar_label(
        _p("Revenue Maturity",
           ["Demand Reality", "Revenue Model Clarity", "Pricing Confidence"], 4)
    )
    assert label == (
        "Revenue Maturity (Demand Reality, Revenue Model Clarity and "
        "Pricing Confidence only)"
    )


def test_unknown_coverage_makes_no_claim():
    """An older report row stored before coverage existed, or a founder whose
    stage could not be resolved. Silence beats a claim we cannot support."""
    assert _pillar_label({"pillar_name": "Team & Leadership"}) == "Team & Leadership"
    assert _pillar_label(_p("Team & Leadership", [], 0)) == "Team & Leadership"


def test_coverage_without_a_total_makes_no_claim():
    assert _pillar_label(_p("Product & Execution", ["Execution Velocity"], 0)) == (
        "Product & Execution"
    )


# --- the label as the founder reads it --------------------------------------

def _slots(pillars):
    return {"overall_band": "Developing", "pillars": pillars,
            "pillars_assessed": len(pillars), "pillars_total": 6}


def test_a_concern_line_carries_the_qualifier():
    """A partially-scoped concern still says what was actually assessed.

    The verdict now renders as a card rather than a sentence, so the qualifier
    rides the card's own scope line instead of the pillar's name -- same claim,
    read in the same glance. Asserted here because a card that dropped it would
    tell a pre-launch founder their whole product was assessed when what was
    assessed was how fast they move.
    """
    pillar = {**_p("Product & Execution", ["Execution Velocity"], 3),
              "band": "Needs Attention"}
    verdicts = _pillar_verdicts([pillar])

    assert "Execution Velocity only" in verdicts
    assert "Needs Attention" in verdicts


def test_the_strongest_list_carries_the_qualifier_too():
    prose = TemplateNarrator()._business_dna(_slots([
        {**_p("Founder Readiness", ["Skill-Stage Fit", "Time Allocation Reality"], 3),
         "band": "Strong"},
        {**_p("Market Clarity", ["a", "b", "c", "d"], 4), "band": "Strong"},
    ]), TONE)

    assert "Skill-Stage Fit and Time Allocation Reality only" in prose
    # The fully-covered one stays bare in the same sentence.
    assert "Market Clarity," in prose or "Market Clarity." in prose


def test_a_fully_scoped_report_reads_exactly_as_it_did():
    """The regression guard. Every pillar at Growth is covered in full, so no
    founder at that stage sees a qualifier anywhere.

    The per-pillar verdict moved out of the prose and into the document's
    verdict list (document._pillar_verdicts) -- six of them joined into one
    paragraph was the least readable block in the report. The qualifier rule is
    unchanged and is asserted in both places, because either one rendering a
    stray "(... only)" is the bug this guards.
    """
    pillars = [
        {**_p("Market Clarity", ["a", "b", "c", "d"], 4), "band": "Strong"},
        {**_p("Team & Leadership", ["a", "b", "c"], 3), "band": "Critical Gap"},
    ]
    prose = TemplateNarrator()._business_dna(_slots(pillars), TONE)
    assert "only)" not in prose

    verdicts = _pillar_verdicts(pillars)
    assert "only" not in verdicts
    assert "Team &amp; Leadership" in verdicts
    assert "Critical Gap" in verdicts


# --- the HTML document ------------------------------------------------------

def test_the_document_note_matches_the_prose_claim():
    assert _coverage_note(_p("P", ["Execution Velocity"], 3)) == "Execution Velocity only"
    assert _coverage_note(_p("P", ["a", "b"], 3)) == "a and b only"
    assert _coverage_note(_p("P", ["a", "b", "c"], 3)) == ""
    assert _coverage_note({"pillar_name": "P"}) == ""


def test_the_bar_carries_coverage_beside_the_weight():
    html = _standing(
        [{"pillar_name": "Product & Execution", "score": 40, "weight": 15,
          **_p("Product & Execution", ["Execution Velocity"], 3)}],
        {},
    )
    assert "15% of overall · Execution Velocity only" in html


def test_the_bar_name_stays_unqualified_so_the_band_lookup_still_works():
    """`_pillar_bands` keys on the pillar's name. Qualifying the name here would
    silently drop the real band from every partial pillar and fall back to the
    score-derived word."""
    html = _standing(
        [{"pillar_name": "Product & Execution", "score": 40, "weight": 15,
          **_p("Product & Execution", ["Execution Velocity"], 3)}],
        {"Product & Execution": "Needs Attention"},
    )
    assert "Needs Attention" in html


def test_an_unassessed_pillar_never_renders_as_a_critical_gap():
    """A pillar with no score is out of scope or too thin -- `_num` floors None
    to 0, which is a Critical gap that SORTS TO THE TOP. This page used to open
    an ideation founder with "Revenue Maturity: Critical gap" for a pillar they
    were never asked about."""
    html = _standing(
        [{"pillar_name": "Market Clarity", "score": 70, "weight": 20},
         {"pillar_name": "Revenue Maturity", "score": None, "weight": 20},
         {"pillar_name": "Team &amp; Leadership", "score": None, "weight": 10}],
        {},
    )
    assert "Revenue Maturity" not in html
    assert "Critical gap" not in html
    assert "Market Clarity" in html


def test_the_document_counts_the_pillars_it_actually_shows():
    """Not hardcoded "Six". Four at ideation, fewer once thin pillars drop."""
    two = _standing([{"pillar_name": "A", "score": 70, "weight": 20},
                     {"pillar_name": "B", "score": 50, "weight": 20}], {})
    assert "Two pillars, weighted by" in two

    one = _standing([{"pillar_name": "A", "score": 70, "weight": 20}], {})
    assert "One pillar, weighted by" in one


def test_a_page_with_nothing_assessed_renders_nothing():
    assert _standing([{"pillar_name": "A", "score": None}], {}) == ""


# --- the scorer attaches it -------------------------------------------------

_BANDS = [{"level": "Strong", "range_min": 0, "range_max": 100}]


def _scored_pillars(stage_order):
    from app.api.v1.reasoning.engines.business_health import (
        BusinessHealthScorer,
        RiskInversionPillarScoreStrategy,
    )

    pillars = [
        SimpleNamespace(pillar_id=p, pillar_name=f"P{p}", pillar_weightage=Decimal("20"),
                        score_bands=_BANDS, red_flag_threshold=None, red_flag_note=None)
        for p in range(1, 7)
    ]
    qs, cls = {}, []
    for qid in range(1, 4):
        qs[qid] = SimpleNamespace(question_id=qid, problem_id=104)
        cls.append(
            SimpleNamespace(
                question_id=qid, score=Decimal("0"), label=ScoreLabel.GREEN
            )
        )
    repo = SimpleNamespace(
        get_readiness_pillars=lambda: pillars,
        get_problems_by_ids=lambda ids: {104: SimpleNamespace(pillar_id=4)},
    )
    founder = SimpleNamespace(stage=SimpleNamespace(stage_order=stage_order))
    context = SimpleNamespace(founder=founder)
    result = BusinessHealthScorer(repo, RiskInversionPillarScoreStrategy()).compute(
        cls, qs, context
    )
    return {p.pillar_id: p for p in result.pillars}


def test_the_scorer_attaches_stage_coverage_to_every_pillar():
    scored = _scored_pillars(IDEATION)

    assert scored[4].dimensions_in_scope == ("Execution Velocity",)
    assert scored[4].dimensions_total == 3
    # Attached to unscored pillars too, so the report can explain their absence.
    assert scored[3].dimensions_in_scope == ()
    assert scored[3].dimensions_total == 4


def test_a_full_stage_reports_every_pillar_as_fully_covered():
    scored = _scored_pillars(FULL)
    for pillar_id, pillar in scored.items():
        assert len(pillar.dimensions_in_scope) == pillar.dimensions_total


def test_an_unknown_stage_makes_no_coverage_claim():
    """Fail open, as everywhere else in scoping: no stage means no claim, not a
    claim of zero coverage."""
    from app.api.v1.reasoning.engines.business_health import (
        BusinessHealthScorer,
        RiskInversionPillarScoreStrategy,
    )

    pillars = [SimpleNamespace(pillar_id=1, pillar_name="P1",
                               pillar_weightage=Decimal("100"), score_bands=_BANDS,
                               red_flag_threshold=None, red_flag_note=None)]
    repo = SimpleNamespace(get_readiness_pillars=lambda: pillars,
                           get_problems_by_ids=lambda ids: {})
    context = SimpleNamespace(founder=SimpleNamespace(stage=None))
    result = BusinessHealthScorer(repo, RiskInversionPillarScoreStrategy()).compute(
        [], {}, context
    )

    assert result.pillars[0].dimensions_in_scope == ()
    assert result.pillars[0].dimensions_total == 0
    assert _pillar_label({"pillar_name": "P1", "dimensions_in_scope": (),
                          "dimensions_total": 0}) == "P1"
