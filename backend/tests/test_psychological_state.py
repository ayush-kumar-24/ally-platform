"""Psychological State (Distress) engine -- unit tests, no DB.

The scorer/engine are deterministic and DB-driven; here the repository is faked so
the weights/signal-id are fixed and the arithmetic + thresholds are asserted.
"""

from decimal import Decimal

from app.api.v1.reasoning.engines.psychological_state import (
    DistressAssessment,
    PsychologicalStateEngine,
    PsychologicalStateSignalScorer,
)
from app.api.v1.reasoning.schemas import AnswerClassification
from app.models.enums import ScoreLabel


class _FakeRepo:
    """Stands in for ReasoningRepository: State-D signals 16..20 (score 5,5,4,3,5)."""

    WEIGHTS = {16: Decimal("5"), 17: Decimal("5"), 18: Decimal("4"), 19: Decimal("3"), 20: Decimal("5")}

    def get_distress_signal_weights(self):
        return dict(self.WEIGHTS)

    def get_acute_distress_signal_id(self):
        # lowest-severity State-D signal (score 3) -> id 19
        return 19

    def get_empathy_protocol(self, code):
        return f"GUIDANCE::{code}"


class _Q:
    def __init__(self, is_distress_tagged):
        self.is_distress_tagged = is_distress_tagged


def _cls(qid, label, *, is_distress_flagged=False):
    return AnswerClassification(
        answer_id=qid, question_id=qid, label=label, score=Decimal("2"),
        is_distress_flagged=is_distress_flagged, is_follow_up=False,
        triggered_follow_up_id=None,
    )


def _engine(high=Decimal("36")):
    repo = _FakeRepo()
    return PsychologicalStateEngine(repo, PsychologicalStateSignalScorer(repo), high)


# --- scorer -----------------------------------------------------------------

def test_scorer_weighted_sum():
    scorer = PsychologicalStateSignalScorer(_FakeRepo())
    # 2 occurrences of signal 16 (5) + 1 of signal 18 (4) = 14
    assert scorer.session_distress_score({"16": 2, "18": 1}) == Decimal("14")


def test_scorer_empty_is_zero():
    assert PsychologicalStateSignalScorer(_FakeRepo()).session_distress_score({}) == Decimal("0")


def test_scorer_ignores_unknown_and_nonpositive():
    scorer = PsychologicalStateSignalScorer(_FakeRepo())
    assert scorer.session_distress_score({"999": 5, "16": 0, "18": -3}) == Decimal("0")


# --- engine: explicit occurrences (the LLM detector's path) -----------------

def test_assess_high_distress_threshold():
    eng = _engine(high=Decimal("36"))
    # 8 x signal 16 (5) = 40 >= 36
    a = eng.assess({"16": 8})
    assert isinstance(a, DistressAssessment)
    assert a.session_distress_score == Decimal("40")
    assert a.is_high_distress is True


def test_assess_below_threshold_not_high():
    a = _engine(high=Decimal("36")).assess({"18": 2})  # 8 < 36
    assert a.session_distress_score == Decimal("8")
    assert a.is_high_distress is False


# --- engine: deterministic fallback from diagnosis --------------------------

def test_single_distress_red_triggers_override_fail_closed():
    # Spec (DISTRESS_SCORE_RED / band 4): ONE distress-tagged Red is a complete
    # override and classifies the session High Distress, regardless of cumulative.
    eng = _engine(high=Decimal("36"))
    a = eng.assess_from_diagnosis([_cls(1, ScoreLabel.RED)], {1: _Q(True)})
    assert a.distress_red_count == 1
    assert a.is_high_distress is True
    assert a.distress_override is True
    # Score floored to the High-Distress threshold so the confidence override fires.
    assert a.session_distress_score == Decimal("36")
    assert a.empathy_protocol_code == "PROMPT-EMPATHY-DISTRESS"
    assert a.empathy_protocol_text == "GUIDANCE::PROMPT-EMPATHY-DISTRESS"


def test_flagged_answer_also_counts():
    eng = _engine()
    qs = {1: _Q(True), 2: _Q(True), 3: _Q(False)}
    cls = [
        _cls(1, ScoreLabel.RED),                            # distress-tagged Red
        _cls(2, ScoreLabel.AMBER),                          # tagged but not Red -> no
        _cls(3, ScoreLabel.RED, is_distress_flagged=True),  # flagged Red -> counts
    ]
    a = eng.assess_from_diagnosis(cls, qs)
    assert a.distress_red_count == 2 and a.is_high_distress is True
    assert a.session_distress_score >= Decimal("36")


def test_deterministic_no_distress_is_zero():
    eng = _engine()
    qs = {1: _Q(False)}
    a = eng.assess_from_diagnosis([_cls(1, ScoreLabel.RED)], qs)
    assert a.signal_occurrences == {}
    assert a.session_distress_score == Decimal("0")
    assert a.is_high_distress is False and a.distress_override is False
    assert a.empathy_protocol_code is None
