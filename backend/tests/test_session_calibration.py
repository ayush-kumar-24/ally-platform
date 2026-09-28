"""The whole-session grade review, and the limits it works inside.

The point of these tests is not that the model can change a grade. It is that
it can only change grades in ways we decided were legitimate -- because this is
the component that would quietly recreate either of the two failures it exists
to prevent, if it drifted.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.reasoning.engines.calibration import SessionCalibrator
from app.api.v1.reasoning.schemas import AnswerClassification
from app.models.enums import ScoreLabel

_BANDS = SimpleNamespace(green=Decimal("0"), amber=Decimal("1"), red=Decimal("2"))


class _Reply:
    def __init__(self, text):
        self._text = text
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        return SimpleNamespace(text=self._text)


class _Boom:
    async def generate(self, request):
        raise RuntimeError("provider is down")


def _classification(answer_id, label):
    return AnswerClassification(
        answer_id=answer_id, question_id=answer_id, label=label,
        score={ScoreLabel.GREEN: Decimal("0"), ScoreLabel.AMBER: Decimal("1"),
               ScoreLabel.RED: Decimal("2"), ScoreLabel.NOT_APPLICABLE: None}[label],
        is_distress_flagged=False, rationale="graded alone",
    )


def _session(labels):
    classifications = [_classification(i, l) for i, l in enumerate(labels, start=1)]
    answers = [SimpleNamespace(answer_id=i, answer_text=f"answer {i}")
               for i in range(1, len(labels) + 1)]
    questions = {i: SimpleNamespace(question_text=f"question {i}")
                 for i in range(1, len(labels) + 1)}
    return classifications, answers, questions


def _run(provider, labels, changes_json):
    classifications, answers, questions = _session(labels)
    calibrator = SessionCalibrator(provider)
    return asyncio.run(
        calibrator.calibrate(classifications, answers, questions, _BANDS)
    ), classifications


def _labels(result):
    return [c.label for c in result]


R, A, G, NA = (ScoreLabel.RED, ScoreLabel.AMBER, ScoreLabel.GREEN,
               ScoreLabel.NOT_APPLICABLE)


# --- the move it exists to make ---------------------------------------------

def test_a_red_the_rest_of_the_session_contradicts_becomes_amber():
    provider = _Reply('{"changes": [{"id": 2, "to": "amber", '
                      '"why": "answers 3 and 4 describe the same weekly sheet"}]}')
    result, _ = _run(provider, [R, R, A, G, A, R], None)
    assert _labels(result) == [R, A, A, G, A, R]
    moved = result[1]
    assert moved.score == Decimal("1")
    assert "session calibration: red -> amber" in moved.rationale
    assert "weekly sheet" in moved.rationale
    assert "graded alone" in moved.rationale, "the original reasoning must survive"


def test_it_can_harshen_too():
    """A pass that can only soften drifts green, which is the failure this
    product already had once."""
    provider = _Reply('{"changes": [{"id": 4, "to": "amber", '
                      '"why": "articulate but describes nothing they do"}]}')
    result, _ = _run(provider, [R, R, A, G, A, R], None)
    assert _labels(result) == [R, R, A, A, A, R]
    assert result[3].score == Decimal("1")


# --- the limits -------------------------------------------------------------

def test_a_two_band_jump_is_refused():
    """red -> green is re-grading. If an answer really is that wrong, the
    per-answer rubric is what needs fixing -- it read the full answer."""
    provider = _Reply('{"changes": [{"id": 1, "to": "green", "why": "nope"}]}')
    result, original = _run(provider, [R, R, A, G, A, R], None)
    assert _labels(result) == _labels(original)


def test_not_applicable_is_untouchable():
    """It means the subject does not exist in this business -- a fact about the
    business, not a severity judgement."""
    provider = _Reply('{"changes": [{"id": 3, "to": "amber", "why": "nope"}]}')
    result, original = _run(provider, [R, A, NA, G, A, R], None)
    assert _labels(result) == _labels(original)


def test_nothing_may_be_moved_to_not_applicable():
    provider = _Reply('{"changes": [{"id": 1, "to": "not_applicable", "why": "nope"}]}')
    result, original = _run(provider, [R, A, A, G, A, R], None)
    assert _labels(result) == _labels(original)


def test_rewriting_more_than_a_third_of_the_session_is_discarded_whole():
    """Not partially applied -- entirely. At that volume the two graders simply
    disagree, and the one that saw each answer in full wins."""
    changes = ", ".join(
        f'{{"id": {i}, "to": "amber", "why": "x"}}' for i in range(1, 4)
    )
    provider = _Reply('{"changes": [' + changes + ']}')
    result, original = _run(provider, [R, R, R, R, R, R], None)
    assert _labels(result) == _labels(original)


def test_exactly_a_third_still_applies():
    changes = ", ".join(
        f'{{"id": {i}, "to": "amber", "why": "x"}}' for i in range(1, 3)
    )
    provider = _Reply('{"changes": [' + changes + ']}')
    result, _ = _run(provider, [R, R, R, R, R, R], None)
    assert _labels(result) == [A, A, R, R, R, R]


# --- failing open -----------------------------------------------------------

def test_a_provider_failure_keeps_every_original_grade():
    result, original = _run(_Boom(), [R, R, A, G, A, R], None)
    assert _labels(result) == _labels(original)


@pytest.mark.parametrize("text", ["", "not json at all", "{}", '{"changes": "nope"}'])
def test_an_unusable_reply_keeps_every_original_grade(text):
    result, original = _run(_Reply(text), [R, R, A, G, A, R], None)
    assert _labels(result) == _labels(original)


def test_an_empty_change_list_is_a_normal_answer():
    """Most sessions need no changes. That must not look like a failure."""
    result, original = _run(_Reply('{"changes": []}'), [R, A, A, G, A, R], None)
    assert _labels(result) == _labels(original)


def test_a_session_with_nothing_to_compare_makes_no_call_at_all():
    provider = _Reply('{"changes": [{"id": 1, "to": "amber", "why": "x"}]}')
    result, original = _run(provider, [R], None)
    assert _labels(result) == _labels(original)
    assert provider.calls == 0


def test_json_in_a_code_fence_is_still_read():
    provider = _Reply('```json\n{"changes": [{"id": 2, "to": "amber", "why": "x"}]}\n```')
    result, _ = _run(provider, [R, R, A, G, A, R], None)
    assert _labels(result)[1] is A


def test_an_unknown_answer_id_is_ignored_rather_than_crashing():
    provider = _Reply('{"changes": [{"id": 999, "to": "amber", "why": "x"}]}')
    result, original = _run(provider, [R, R, A, G, A, R], None)
    assert _labels(result) == _labels(original)
