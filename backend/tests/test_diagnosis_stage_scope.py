"""Stage scoping: what a founder's stage may be diagnosed on.

The pillar round-robin gives every pillar its turn, which is what stopped
Founder Psychology draining the whole budget -- but it also walked a pre-launch
solo founder through Revenue Maturity and Team & Leadership. Measured against
the live Stage 0 bank, 20 of an ideation founder's 30 questions landed outside
Founder DNA and Idea Validation.

These tests hold the scope table to `GoXL_Business_DNA` Part 3 rather than to a
rule of our own. The previous table was derived from "what actually exists yet"
-- a paying customer, a product a stranger uses, a person who is not the founder
-- which is reasonable and disagreed with Part 3 at every stage below Early
Traction. `test_the_scope_table_is_part_3` is the one that would have caught it.

Scope removes candidates rather than reordering them, because the ranking bias
only reorders and an out-of-scope question would still surface once the in-scope
ones ran out -- exactly the budget tail an ideation founder reaches.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.business_dna import (
    ALL_DIMENSION_CODES,
    DIMENSION_BY_CODE,
    IDEATION_CATEGORIES,
    PILLAR_BY_CATEGORY,
    dimensions_in,
)
from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.stage_scope import (
    ALL_PILLARS,
    FOUNDER_READINESS,
    MARKET_CLARITY,
    PRODUCT_AND_EXECUTION,
    REVENUE_MATURITY,
    SCOPE_BY_STAGE_ORDER,
    STRATEGIC_CLARITY,
    TEAM_AND_LEADERSHIP,
    resolve_scope,
    scope_for,
)

#: problem_id -> pillar_id, one problem per pillar so a question's pillar is
#: readable straight off its problem_id.
_PILLAR_MAP = {10 + pid: pid for pid in sorted(ALL_PILLARS)}

#: A category that is in scope everywhere, so a test about pillars is not
#: silently also a test about categories.
_NEUTRAL_CATEGORY = "Idea & Validation"


def _q(qid, pillar, category=_NEUTRAL_CATEGORY, priority="CORE", difficulty=1):
    return SimpleNamespace(
        question_id=qid, problem_id=10 + pillar, root_cause_id=None,
        category=category, priority=priority, difficulty_level=difficulty,
    )


def _founder(stage_order):
    stage = SimpleNamespace(stage_order=stage_order) if stage_order else None
    return SimpleNamespace(founder_id=1, stage=stage)


def _engine(candidates, *, pillar_map=_PILLAR_MAP, pillar_map_raises=False):
    def problem_to_pillar():
        if pillar_map_raises:
            raise RuntimeError("db down")
        return pillar_map

    return QuestionSelectionEngine(SimpleNamespace(
        list_candidate_questions=lambda **kw: list(candidates),
        problem_to_pillar=problem_to_pillar,
        answered_count_per_pillar_category=lambda session_id: {},
        get_detected_root_cause_ids=lambda session_id: set(),
    ))


def _session():
    return SimpleNamespace(session_id=1, routing_state="continue")


_ONE_PER_PILLAR = [_q(pid, pid) for pid in sorted(ALL_PILLARS)]

IDEATION, EARLY, FULL = 1, 2, 5


# --- Part 2: the model itself ----------------------------------------------

def test_part_2_has_six_pillars_and_twenty_dimensions():
    assert len(ALL_PILLARS) == 6
    assert len(ALL_DIMENSION_CODES) == 20


def test_every_dimension_belongs_to_a_real_pillar():
    assert {d.pillar_id for d in DIMENSION_BY_CODE.values()} == set(ALL_PILLARS)


def test_the_pillars_are_sized_as_part_2_describes_them():
    """Market Clarity and Revenue Maturity carry four dimensions each; the
    other four pillars carry three. 4 + 4 + 3*4 = 20."""
    assert len(dimensions_in(MARKET_CLARITY)) == 4
    assert len(dimensions_in(REVENUE_MATURITY)) == 4
    for pillar in (FOUNDER_READINESS, PRODUCT_AND_EXECUTION,
                   TEAM_AND_LEADERSHIP, STRATEGIC_CLARITY):
        assert len(dimensions_in(pillar)) == 3


# --- Part 3: the stage table -----------------------------------------------

def test_every_stage_has_a_scope():
    """All eight periods are covered -- no stage falls through to 'unscoped'."""
    assert sorted(SCOPE_BY_STAGE_ORDER) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_the_scope_table_is_part_3():
    """The dimension counts Part 3 states, verbatim:

        Stage 0      "9 dimensions total"
        Stage 0->1   "All 20 dimensions become live except Revenue
                      Concentration and Hiring Repeatability"
        Stage 1->10+ "All 20 dimensions apply."
    """
    assert len(SCOPE_BY_STAGE_ORDER[IDEATION].dimensions) == 9
    assert len(SCOPE_BY_STAGE_ORDER[EARLY].dimensions) == 18
    assert len(SCOPE_BY_STAGE_ORDER[FULL].dimensions) == 20


def test_ideation_is_the_nine_dimensions_part_3_names():
    """Market Clarity in full, 2 of 3 from Founder Readiness and Strategic
    Clarity, and Execution Velocity alone from Product & Execution."""
    live = SCOPE_BY_STAGE_ORDER[IDEATION].dimensions

    assert dimensions_in(MARKET_CLARITY) <= live
    assert live & dimensions_in(FOUNDER_READINESS) == {
        "skill_stage_fit", "time_allocation_reality"
    }
    assert live & dimensions_in(STRATEGIC_CLARITY) == {
        "plan_to_vision_alignment", "prioritization_discipline"
    }
    assert live & dimensions_in(PRODUCT_AND_EXECUTION) == {"execution_velocity"}
    assert not live & dimensions_in(REVENUE_MATURITY)
    assert not live & dimensions_in(TEAM_AND_LEADERSHIP)


def test_ideation_reaches_four_pillars_not_two():
    """The regression this change fixes. Product & Execution and Strategic
    Clarity were withheld entirely, taking Execution Velocity, Plan-to-Vision
    Alignment and Prioritization Discipline with them -- three of the nine
    dimensions Part 3 puts at Stage 0, and 98 of the 245 questions in the
    shipped Stage 0 bank."""
    assert SCOPE_BY_STAGE_ORDER[IDEATION].pillars == {
        FOUNDER_READINESS, MARKET_CLARITY, PRODUCT_AND_EXECUTION, STRATEGIC_CLARITY
    }


@pytest.mark.parametrize("stage_order", [2, 3, 4])
def test_stage_0_to_1_is_one_band_on_every_pillar(stage_order):
    """Part 3 treats Validation, Prototype and Early Traction as ONE band. The
    previous table split them across three different pillar sets, withholding
    Team & Leadership and Strategic Clarity from the first two."""
    scope = SCOPE_BY_STAGE_ORDER[stage_order]
    assert scope.covers_all_pillars
    assert scope.excluded_dimensions == {"revenue_concentration", "hiring_repeatability"}


@pytest.mark.parametrize("stage_order", [5, 6, 7, 8])
def test_growth_onward_is_every_dimension(stage_order):
    scope = SCOPE_BY_STAGE_ORDER[stage_order]
    assert scope.covers_all_pillars
    assert scope.excluded_dimensions == frozenset()


def test_scope_widens_monotonically_through_the_stages():
    """A stage never loses a dimension the stage before it had."""
    for earlier, later in zip(range(1, 8), range(2, 9)):
        assert (SCOPE_BY_STAGE_ORDER[earlier].dimensions
                <= SCOPE_BY_STAGE_ORDER[later].dimensions)


def test_the_two_dimension_exclusions_are_recorded_even_though_unenforceable():
    """`questions` has no dimension column, so Revenue Concentration and Hiring
    Repeatability cannot be filtered out of candidates. They are carried on the
    scope so the report can say they were deliberately not assessed -- and so
    the day that column exists, this is a filter change and not a redesign."""
    assert SCOPE_BY_STAGE_ORDER[EARLY].excluded_dimensions == {
        "revenue_concentration", "hiring_repeatability"
    }
    # Both belong to pillars that ARE in scope, which is exactly why a pillar
    # set cannot express them.
    assert DIMENSION_BY_CODE["revenue_concentration"].pillar_id in SCOPE_BY_STAGE_ORDER[EARLY].pillars
    assert DIMENSION_BY_CODE["hiring_repeatability"].pillar_id in SCOPE_BY_STAGE_ORDER[EARLY].pillars


# --- the category axis ------------------------------------------------------

def test_ideation_withholds_the_execution_categories():
    """A founder with no product, no channel, no customer and no team is not
    asked about running any of them."""
    categories = SCOPE_BY_STAGE_ORDER[IDEATION].categories
    assert categories is not None
    for withheld in ("Marketing Execution", "Go-To-Market", "Sales Execution",
                     "Sales & Revenue", "Financial Management",
                     "Team & Leadership", "Scaling & Operational Maturity",
                     "Fundraising"):
        assert withheld not in categories


def test_ideation_keeps_the_categories_its_live_dimensions_need():
    assert SCOPE_BY_STAGE_ORDER[IDEATION].categories == IDEATION_CATEGORIES
    for kept in ("Founder Psychology", "Idea & Validation", "Competitive Awareness",
                 "Opportunity Evaluation", "Business Planning", "Product"):
        assert kept in IDEATION_CATEGORIES


@pytest.mark.parametrize("stage_order", [2, 3, 4, 5, 6, 7, 8])
def test_every_stage_past_ideation_withholds_no_category(stage_order):
    """Part 3 puts all six pillars in scope from Validation on, so there is
    nothing left to withhold -- and a category seeded later must not be
    silently dropped at stages that withhold nothing."""
    assert SCOPE_BY_STAGE_ORDER[stage_order].categories is None
    assert SCOPE_BY_STAGE_ORDER[stage_order].withholds_nothing


def test_the_category_axis_is_not_implied_by_the_pillar_axis():
    """The measurement this whole second filter exists for. Marketing Execution
    scores Market Clarity, which is FULLY in scope at ideation -- so pillar
    scope alone would admit it."""
    assert PILLAR_BY_CATEGORY["Marketing Execution"] == MARKET_CLARITY
    assert MARKET_CLARITY in SCOPE_BY_STAGE_ORDER[IDEATION].pillars
    assert "Marketing Execution" not in SCOPE_BY_STAGE_ORDER[IDEATION].categories


# --- resolution ------------------------------------------------------------

def test_unknown_stage_leaves_everything_in_scope():
    """Fail open, same convention as stage_groups_for: narrowing a founder we
    cannot place would silently under-diagnose them."""
    assert resolve_scope(_founder(None)) is None
    assert scope_for(None) is None
    assert scope_for(SimpleNamespace()) is None


def test_a_stage_order_outside_the_table_is_unscoped():
    assert scope_for(SimpleNamespace(stage_order=99)) is None


# --- filtering: pillars -----------------------------------------------------

def test_ideation_never_sees_revenue_or_team_questions():
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(IDEATION))
    pillars = {q.problem_id - 10 for q in got}
    assert REVENUE_MATURITY not in pillars
    assert TEAM_AND_LEADERSHIP not in pillars


def test_ideation_does_see_product_and_strategy_questions():
    """The other half of the fix: these used to be dropped."""
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(IDEATION))
    pillars = {q.problem_id - 10 for q in got}
    assert PRODUCT_AND_EXECUTION in pillars
    assert STRATEGIC_CLARITY in pillars


@pytest.mark.parametrize("stage_order", [2, 3, 4])
def test_the_whole_early_band_keeps_every_pillar(stage_order):
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(stage_order))
    assert {q.problem_id - 10 for q in got} == set(ALL_PILLARS)


def test_a_full_scope_stage_keeps_every_candidate():
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(FULL))
    assert len(got) == len(_ONE_PER_PILLAR)


def test_selection_only_ever_returns_an_in_scope_question():
    """End to end through the ranking, not just the filter."""
    engine = _engine(_ONE_PER_PILLAR)
    picked = engine.select_next_question(_session(), _founder(IDEATION))
    assert _PILLAR_MAP[picked.problem_id] in SCOPE_BY_STAGE_ORDER[IDEATION].pillars


# --- filtering: categories --------------------------------------------------

@pytest.mark.parametrize(
    "category",
    ["Marketing Execution", "Go-To-Market", "Sales Execution", "Sales & Revenue",
     "Financial Management", "Team & Leadership", "Scaling & Operational Maturity"],
)
def test_an_ideation_founder_is_never_asked_an_execution_question(category):
    """The rule stated directly. Each of these is paired with a pillar that IS
    in scope at ideation, so only the category test can remove it."""
    pillar = PILLAR_BY_CATEGORY[category]
    in_scope_pillar = pillar in SCOPE_BY_STAGE_ORDER[IDEATION].pillars
    candidates = [
        _q(1, pillar, category=category),
        _q(2, MARKET_CLARITY, category="Idea & Validation"),
    ]
    engine = _engine(candidates)
    got = engine.candidate_questions(_session(), _founder(IDEATION))

    assert [q.question_id for q in got] == [2]
    # If this is False the pillar test would have caught it anyway and the
    # parametrised case proves nothing -- assert the interesting ones exist.
    if category in ("Marketing Execution", "Go-To-Market"):
        assert in_scope_pillar


def test_the_same_question_is_fair_game_one_stage_later():
    """Category scope is about the founder's stage, not about the question.

    Paired with an in-scope question deliberately: a candidate set holding
    nothing BUT the marketing question would trip the never-starve fallback and
    come back unfiltered, which is correct behaviour and not what this asserts.
    """
    marketing = _q(1, MARKET_CLARITY, category="Marketing Execution")
    idea = _q(2, MARKET_CLARITY, category="Idea & Validation")
    engine = _engine([marketing, idea])

    assert engine.candidate_questions(_session(), _founder(IDEATION)) == [idea]
    assert engine.candidate_questions(_session(), _founder(EARLY)) == [marketing, idea]


def test_an_unknown_category_is_still_withheld_at_ideation():
    """Ideation is an allow-list on purpose: a category seeded later has to be
    admitted deliberately rather than arrive by default, because ideation is
    where an off-topic question costs most."""
    engine = _engine([
        _q(1, MARKET_CLARITY, category="Partnerships & BD"),
        _q(2, MARKET_CLARITY, category="Idea & Validation"),
    ])
    got = engine.candidate_questions(_session(), _founder(IDEATION))
    assert [q.question_id for q in got] == [2]


def test_an_unknown_category_is_admitted_past_ideation():
    """...and everywhere else it fails open, so seeding a new category does not
    silently delete it from the bank."""
    engine = _engine([_q(1, MARKET_CLARITY, category="Partnerships & BD")])
    got = engine.candidate_questions(_session(), _founder(EARLY))
    assert [q.question_id for q in got] == [1]


# --- degrade paths: scope must never end a diagnosis early -----------------

def test_an_unavailable_pillar_map_still_applies_the_category_filter():
    """The two tests degrade independently. Losing the database lookup must not
    hand an ideation founder the revenue and marketing questions."""
    engine = _engine(
        [
            _q(1, MARKET_CLARITY, category="Marketing Execution"),
            _q(2, MARKET_CLARITY, category="Idea & Validation"),
        ],
        pillar_map_raises=True,
    )
    got = engine.candidate_questions(_session(), _founder(IDEATION))
    assert [q.question_id for q in got] == [2]


def test_an_unavailable_pillar_map_drops_only_the_pillar_test():
    """A revenue question with an in-scope category survives, because nothing
    can tell which pillar it belongs to. Over-asking is the recoverable side."""
    engine = _engine(
        [_q(1, REVENUE_MATURITY, category="Idea & Validation")],
        pillar_map_raises=True,
    )
    got = engine.candidate_questions(_session(), _founder(IDEATION))
    assert len(got) == 1


def test_an_empty_pillar_map_behaves_like_an_unavailable_one():
    engine = _engine(
        [_q(1, REVENUE_MATURITY, category="Idea & Validation")], pillar_map={}
    )
    assert len(engine.candidate_questions(_session(), _founder(IDEATION))) == 1


def test_scope_matching_nothing_falls_back_rather_than_starving():
    """A bank with no in-scope question is a data problem. Ending the founder's
    diagnosis over it is worse than asking something off-topic."""
    only_out_of_scope = [
        _q(1, REVENUE_MATURITY, category="Financial Management"),
        _q(2, TEAM_AND_LEADERSHIP, category="Team & Leadership"),
    ]
    engine = _engine(only_out_of_scope)
    got = engine.candidate_questions(_session(), _founder(IDEATION))
    assert len(got) == 2


def test_no_candidates_stays_no_candidates():
    """An exhausted bank must still report exhaustion -- that is the completion
    signal, and scope must not turn it into anything else."""
    engine = _engine([])
    assert engine.candidate_questions(_session(), _founder(IDEATION)) == []
