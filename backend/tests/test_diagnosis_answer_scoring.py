"""A kept answer is never left unscored.

An unscored answer is not neutral. StoredScoreAnswerClassifier refuses to guess
a band, so classify_answers logs "Skipping unscored answer" and drops it: the
founder's answer is accepted, shown back to them as answered, and then
contributes nothing to their diagnosis. Measured on one live session, six
answers went that way. Enough of them and NoClassifiableAnswersError takes the
whole report down with a 422.

submit_answer guards against that with a neutral AMBER fallback -- and the
guard had a hole. It asked `insight is None`, on the assumption that an
advisor insight always carries a usable band. advisor._parse deliberately
breaks that assumption: a label outside {green, amber, red} nulls score_label
while still returning the insight, because the responsiveness verdict and the
next-question pick in the same reply are still good. In that state
_apply_insight no-ops and the `else` never runs, so the exact silent data loss
the fallback exists to prevent happened anyway -- just via a different route
than an advisor outage.

The predicate is about the SCORE, not the object carrying it.
"""

from __future__ import annotations

from app.api.v1.diagnosis.advisor import AnswerInsight, LLMNextQuestionAdvisor
from app.api.v1.diagnosis.service import needs_fallback_score


def _parse(payload: str) -> AnswerInsight | None:
    return LLMNextQuestionAdvisor.__dict__["_parse"](
        LLMNextQuestionAdvisor(provider=None), payload
    )


# --- the hole this closes ---------------------------------------------------

def test_an_unparseable_label_takes_the_fallback():
    """The regression. A non-vocabulary label is exactly the case that fell
    between the two branches."""
    insight = _parse('{"score_label":"moderate","confidence":0.7,"next_question_id":3}')
    assert insight is not None, "the insight itself survives -- only the band is dropped"
    assert insight.score_label is None
    assert needs_fallback_score(insight) is True


def test_a_missing_label_takes_the_fallback():
    insight = _parse('{"confidence":0.7,"next_question_id":3}')
    assert insight is not None
    assert needs_fallback_score(insight) is True


# --- the cases that already worked, pinned so they keep working -------------

def test_no_insight_at_all_takes_the_fallback():
    """No advisor wired, or the call failed/timed out."""
    assert needs_fallback_score(None) is True


def test_a_real_band_is_kept():
    for label in ("green", "amber", "red"):
        insight = _parse(f'{{"score_label":"{label}","confidence":0.8}}')
        assert insight is not None
        assert insight.score_label is not None
        assert needs_fallback_score(insight) is False, label


def test_an_answer_judged_unresponsive_but_scored_keeps_its_score():
    """Responsiveness and quality are separate axes. An answer accepted over the
    one-reprompt bound still carries the band the model gave it."""
    insight = _parse('{"score_label":"red","responsive":false}')
    assert insight is not None
    assert needs_fallback_score(insight) is False
