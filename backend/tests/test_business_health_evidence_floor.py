"""A pillar needs enough answers before it gets a band.

A pillar's score is the mean of its answers' risk (0 green / 1 amber / 2 red)
inverted onto 0-100, so the number of answers IS the resolution of the score.
One answer can only ever produce 0, 50 or 100. Two can produce five values. And
the founder is never shown the sample size -- the report prints a BAND, so
"Critical Gap" off a single amber answer reads exactly like "Critical Gap" off
eight.

That was tolerable while thin pillars were rare. Stage scoping and the ideation
Business Health Score make them routine: an ideation founder is diagnosed on
four pillars from a 20-question budget, and one who abandons early leaves some
of them with very little. So a pillar below the floor is now reported the same
way as one that was never asked -- no score, no band, no red flag, and excluded
from the overall, which renormalises over what remains.

The two cases stay distinguishable downstream: `assessed_question_count` is 0
for never-asked and 1-2 for below-floor.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.reasoning.engines.business_health import (
    BusinessHealthScorer,
    RiskInversionPillarScoreStrategy,
)
from app.core.config import settings

_BANDS = [
    {"level": "Critical Gap", "range_min": 0, "range_max": 35},
    {"level": "Needs Attention", "range_min": 36, "range_max": 55},
    {"level": "Developing", "range_min": 56, "range_max": 75},
    {"level": "Strong", "range_min": 76, "range_max": 100},
]


def _pillar(pillar_id, weight):
    return SimpleNamespace(
        pillar_id=pillar_id, pillar_name=f"Pillar {pillar_id}",
        pillar_weightage=Decimal(str(weight)), score_bands=_BANDS,
        red_flag_threshold=35, red_flag_note="flagged",
    )


#: Six pillars, weights summing to 100 as the database trigger requires.
_PILLARS = [_pillar(1, 25), _pillar(2, 20), _pillar(3, 20),
            _pillar(4, 15), _pillar(5, 10), _pillar(6, 10)]


def _scorer(answers_per_pillar):
    """answers_per_pillar: {pillar_id: [risk scores]}. Wires the question ->
    problem -> pillar chain the scorer reads, one problem per pillar."""
    classifications, questions = [], {}
    qid = 0
    for pillar_id, scores in answers_per_pillar.items():
        for score in scores:
            qid += 1
            questions[qid] = SimpleNamespace(question_id=qid, problem_id=100 + pillar_id)
            classifications.append(
                SimpleNamespace(question_id=qid, score=Decimal(str(score)))
            )
    problems = {
        100 + p: SimpleNamespace(pillar_id=p) for p in answers_per_pillar
    }
    repo = SimpleNamespace(
        get_readiness_pillars=lambda: _PILLARS,
        get_problems_by_ids=lambda ids: problems,
    )
    scorer = BusinessHealthScorer(repo, RiskInversionPillarScoreStrategy())
    return scorer.compute(classifications, questions, context=None)


def _by_id(result):
    return {p.pillar_id: p for p in result.pillars}


# --- the floor --------------------------------------------------------------

def test_the_floor_is_three():
    assert settings.MIN_ANSWERS_PER_PILLAR_SCORE == 3


@pytest.mark.parametrize("n", [1, 2])
def test_a_pillar_under_the_floor_gets_no_band(n):
    result = _scorer({1: [0] * n, 2: [0, 0, 0]})
    thin = _by_id(result)[1]

    assert thin.score is None
    assert thin.band is None
    assert thin.red_flag_triggered is False


@pytest.mark.parametrize("n", [1, 2])
def test_a_pillar_under_the_floor_still_reports_its_real_count(n):
    """This is what separates "asked twice" from "never asked" downstream."""
    assert _by_id(_scorer({1: [0] * n, 2: [0, 0, 0]}))[1].assessed_question_count == n


def test_a_pillar_at_the_floor_is_scored():
    scored = _by_id(_scorer({1: [0, 0, 0]}))[1]
    assert scored.score == Decimal("100")
    assert scored.band == "Strong"
    assert scored.assessed_question_count == 3


def test_a_never_asked_pillar_is_still_reported_with_a_zero_count():
    assert _by_id(_scorer({1: [0, 0, 0]}))[5].assessed_question_count == 0


# --- what the floor does to the headline score ------------------------------

def test_a_thin_pillar_is_excluded_from_the_overall():
    """The whole point. One red answer on a 25-weight pillar used to drag the
    headline score down by a quarter on the strength of a single question."""
    with_thin = _scorer({1: [2], 2: [0, 0, 0]})
    without = _scorer({2: [0, 0, 0]})

    assert with_thin.overall_score == without.overall_score == Decimal("100")


def test_the_overall_renormalises_over_what_survived_the_floor():
    """Pillar 2 (weight 20) all green, pillar 3 (weight 20) all red, pillar 1
    thin. The survivors carry equal weight, so the overall is the midpoint --
    not dragged by pillar 1 and not rescued by it either."""
    result = _scorer({1: [2, 2], 2: [0, 0, 0], 3: [2, 2, 2]})

    assert _by_id(result)[1].score is None
    assert result.overall_score == Decimal("50")


def test_a_session_too_thin_everywhere_scores_nothing_rather_than_guessing():
    """Every pillar under the floor means no weight survives. The scorer returns
    0 with no band, which the report renders as no claim at all -- rather than
    inventing a number from two answers."""
    result = _scorer({1: [0], 2: [0], 3: [2]})

    assert all(p.score is None for p in result.pillars)
    assert result.band is None


def test_a_thin_pillar_cannot_raise_a_red_flag():
    """A red flag is the strongest claim the score makes, and it drives the
    report's Section H. Two red answers must not trigger one."""
    result = _scorer({1: [2, 2], 2: [0, 0, 0]})

    assert _by_id(result)[1].red_flag_triggered is False
    assert result.red_flags == ()


def test_a_pillar_over_the_floor_can_still_raise_a_red_flag():
    """The floor must not have disabled red flags altogether."""
    result = _scorer({1: [2, 2, 2]})

    assert _by_id(result)[1].red_flag_triggered is True
    assert "Pillar 1" in result.red_flags


# --- ideation, which is why this exists -------------------------------------

def test_a_full_ideation_session_scores_all_four_of_its_pillars():
    """Budget 20 over the four pillars Part 3 puts at ideation is five answers
    each -- comfortably clear of the floor."""
    result = _scorer({1: [0] * 5, 2: [0] * 5, 4: [1] * 5, 6: [1] * 5})
    scored = [p for p in result.pillars if p.score is not None]

    assert {p.pillar_id for p in scored} == {1, 2, 4, 6}
    assert result.overall_score is not None


def test_an_abandoned_ideation_session_narrows_rather_than_misleads():
    """A founder who stops after eight answers leaves two pillars thin. Those
    drop out; the two with enough answers still report."""
    result = _scorer({1: [0] * 3, 2: [0] * 3, 4: [2], 6: [2]})
    scored = {p.pillar_id for p in result.pillars if p.score is not None}

    assert scored == {1, 2}
    assert _by_id(result)[4].score is None
    assert _by_id(result)[6].score is None
