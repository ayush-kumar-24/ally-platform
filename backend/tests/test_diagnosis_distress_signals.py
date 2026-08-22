"""Distress signals: two independent routes, not one route with a modifier.

distress_signal_answers has always documented itself as "Red answers on
distress-tagged questions, OR answers explicitly flagged for distress". The
code ANDed them -- a `continue` on any non-Red label sat above the tag check,
so the explicit flag could only ever act as a modifier on a Red score and never
qualify an answer on its own.

Those two readings produce materially different reports. An explicit distress
flag is a direct signal about the person; a Green or Amber band is a statement
about their BUSINESS answer. A founder whose answers carried the flag but
scored Amber never tripped distress mode and was handed the standard report --
opening with a health ring and a root-cause verdict rather than the wellbeing
copy the distress variant exists for.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.api.v1.reasoning.engines.diagnostic import StandardDiagnosticEngine
from app.api.v1.reasoning.schemas import AnswerClassification
from app.models.enums import ScoreLabel


class _Question:
    def __init__(self, question_id: int, is_distress_tagged: bool):
        self.question_id = question_id
        self.is_distress_tagged = is_distress_tagged


def _classification(answer_id: int, question_id: int, label: ScoreLabel,
                    flagged: bool = False) -> AnswerClassification:
    return AnswerClassification(
        answer_id=answer_id, question_id=question_id, label=label,
        score=Decimal("1"), is_distress_flagged=flagged,
    )


@pytest.fixture
def engine() -> StandardDiagnosticEngine:
    return StandardDiagnosticEngine(classifier=None)  # only the pure method is used


def _signals(engine, classifications, questions) -> list[int]:
    return engine.distress_signal_answers(classifications, questions, context=None)


# --- route 1: an explicit flag stands on its own ----------------------------

def test_an_explicitly_flagged_amber_answer_counts():
    """The regression. This answer used to count for nothing."""
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(
        engine,
        [_classification(1, 10, ScoreLabel.AMBER, flagged=True)],
        {10: _Question(10, is_distress_tagged=False)},
    )
    assert signals == [1]


def test_an_explicitly_flagged_green_answer_counts():
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(
        engine,
        [_classification(2, 11, ScoreLabel.GREEN, flagged=True)],
        {11: _Question(11, is_distress_tagged=False)},
    )
    assert signals == [2]


def test_an_explicit_flag_counts_even_with_no_question_row():
    """The flag is on the ANSWER, so it does not depend on resolving the
    question it was given to."""
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(engine, [_classification(3, 99, ScoreLabel.AMBER, flagged=True)], {})
    assert signals == [3]


# --- route 2: Red on a distress-tagged question -----------------------------

def test_red_on_a_distress_tagged_question_counts():
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(
        engine,
        [_classification(4, 12, ScoreLabel.RED)],
        {12: _Question(12, is_distress_tagged=True)},
    )
    assert signals == [4]


# --- neither route: still nothing -------------------------------------------

def test_red_on_an_untagged_question_does_not_count():
    """A bad business answer is not distress. This is the guard that keeps the
    distress variant from firing on a merely poor diagnosis."""
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(
        engine,
        [_classification(5, 13, ScoreLabel.RED)],
        {13: _Question(13, is_distress_tagged=False)},
    )
    assert signals == []


def test_amber_on_a_tagged_question_without_the_flag_does_not_count():
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(
        engine,
        [_classification(6, 14, ScoreLabel.AMBER)],
        {14: _Question(14, is_distress_tagged=True)},
    )
    assert signals == []


def test_an_answer_qualifying_on_both_routes_is_counted_once():
    engine = StandardDiagnosticEngine(classifier=None)
    signals = _signals(
        engine,
        [_classification(7, 15, ScoreLabel.RED, flagged=True)],
        {15: _Question(15, is_distress_tagged=True)},
    )
    assert signals == [7]
