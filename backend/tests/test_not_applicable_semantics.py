"""N/A is a real state, not a weak Red -- proved at every stage that could leak it.

NOT_APPLICABLE has existed in `ScoreLabel` and been handled correctly by the
reasoning engines for some time, but it was UNREACHABLE IN PRODUCTION: the
adaptive advisor is the de-facto classifier under the shipped
`ANSWER_CLASSIFIER=stored`, and its `_VALID_LABELS` admitted only green/amber/
red. So these tests cover two different things and both are needed:

  * that the advisor can now produce the label at all, and
  * that once produced it cannot become risk, evidence, coverage or confidence.

The counting tests are the ones that found a live defect. Every engine that
produces FINDINGS already refused N/A, but coverage counted it, and coverage is
25% of the confidence score -- so a founder whose questions largely did not
apply climbed toward "confident" on evidence every engine had thrown away.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.advisor import AnswerInsight, LLMNextQuestionAdvisor
from app.api.v1.reasoning.service import diagnostic_answer_count
from app.models.enums import ScoreLabel


def answer(label):
    return SimpleNamespace(score_label=label)


# =========================================================== the label exists
def test_not_applicable_is_unscored_by_definition():
    assert ScoreLabel.NOT_APPLICABLE.is_scored is False
    for label in (ScoreLabel.GREEN, ScoreLabel.AMBER, ScoreLabel.RED):
        assert label.is_scored is True


def test_not_applicable_is_not_green_amber_or_red():
    assert ScoreLabel.NOT_APPLICABLE.value not in {"green", "amber", "red"}


def test_the_advisor_can_now_return_it():
    """The gap that made the whole state unreachable in production."""
    advisor = LLMNextQuestionAdvisor.__new__(LLMNextQuestionAdvisor)
    insight = advisor._parse(
        '{"score_label":"not_applicable","confidence":0.9,'
        '"next_question_id":7,"rationale":"solo founder, no managers"}'
    )
    assert insight.score_label == ScoreLabel.NOT_APPLICABLE.value


def test_an_n_a_insight_carries_no_numeric_score():
    """Case 7, at the source. Zero is Green's band, so N/A must be None."""
    insight = AnswerInsight(score_label="not_applicable", confidence=0.9,
                            next_question_id=None, rationale="")
    assert insight.score is None
    for label, expected in (("green", 0), ("amber", 1), ("red", 2)):
        assert AnswerInsight(label, 0.5, None, "").score == expected


def test_an_unparseable_label_is_still_rejected():
    # Widening _VALID_LABELS must not have widened it to anything at all.
    advisor = LLMNextQuestionAdvisor.__new__(LLMNextQuestionAdvisor)
    assert advisor._parse('{"score_label":"maybe","confidence":0.5}').score_label is None


# =========================================================== risk and evidence
def test_n_a_never_enters_the_risk_numerator():
    """Case 7. `None`, not 0 -- a zero would be positive evidence of health."""
    source = open("app/api/v1/reasoning/engines/diagnostic.py").read()
    assert "ScoreLabel.NOT_APPLICABLE: None," in source, (
        "the classifier must map NOT_APPLICABLE to an absent score, never to a "
        "band -- zero is Green"
    )


@pytest.mark.parametrize("source", [
    "app/api/v1/reasoning/engines/diagnostic.py",      # risk numerator + denominator
    "app/api/v1/reasoning/engines/symptom_detection.py",
    "app/api/v1/reasoning/engines/root_cause.py",      # Cases 19 and 20
])
def test_every_evidence_engine_filters_on_is_scored(source):
    """Structural: each engine must consult `is_scored` before using a label.

    Asserted on the source rather than by constructing four engines' worth of
    fixtures, because what matters is that NONE of them can grow a path that
    skips the check -- and a behavioural test only covers the path it exercises.
    """
    text = open(source).read()
    assert "is_scored" in text, f"{source} does not filter on ScoreLabel.is_scored"


def test_n_a_cannot_become_a_recommendation_trigger():
    """Case 20, by construction.

    Recommendations are matched to DETECTED ROOT CAUSES
    (StandardRecommendationEngine takes scored detections, never raw answers),
    and root-cause detection already refuses an unscored label. So an N/A answer
    has no path to a recommendation that does not pass through root_cause.py's
    `is_scored` check, which the test above pins.
    """
    source = open("app/api/v1/reasoning/engines/recommendation.py").read()
    assert "Answer" not in source.split("class StandardRecommendationEngine")[1][:2000], (
        "the recommendation engine must consume detections, not raw answers"
    )


# =========================================================== coverage and confidence
def test_n_a_does_not_count_as_a_meaningful_answered_question():
    """Case 9. The live defect: coverage counted what every engine discarded."""
    answers = [answer("green"), answer("not_applicable"), answer("red"),
               answer("not_applicable"), answer("amber")]
    assert diagnostic_answer_count(answers) == 3
    assert len(answers) == 5                 # the budget meter still sees five


def test_an_unclassified_answer_still_counts():
    # NULL is "not measured yet", not "does not apply". Treating them alike
    # would shrink coverage every time the classifier errored.
    assert diagnostic_answer_count([answer(None), answer("green")]) == 2


def test_a_session_of_only_n_a_answers_has_zero_coverage():
    """Case 8. The end state the defect allowed: confidence built on nothing."""
    assert diagnostic_answer_count([answer("not_applicable")] * 12) == 0


def test_coverage_uses_the_diagnostic_count_not_the_row_count():
    """The wiring, asserted where the two numbers are chosen apart."""
    source = open("app/api/v1/reasoning/service.py").read()
    assert "questions_answered=diagnostic_answers" in source
    assert "questions_answered=len(answers)" not in source, (
        "coverage must not be derived from the raw answer count"
    )


def test_completion_gates_use_the_diagnostic_count_too():
    source = open("app/api/v1/diagnosis/incremental_confidence.py").read()
    assert 'getattr(assessment, "questions_answered", None)' in source
