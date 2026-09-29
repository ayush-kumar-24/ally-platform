"""A founder who does not understand a question is helped, never scored.

Founders reported they could not follow what Ally was asking. What happened when
they said so was worse than the wording: "I don't understand the question" was
either scored like "I don't know" -- Red, the strongest negative signal, for
Ally's own phrasing -- or rejected with a line telling them they had answered a
different question.

Now the advisor call the phase already makes flags the confusion and writes a
plainer rewording in the same reply, so this costs no extra LLM call. The
properties pinned here:
  * it fails CLOSED toward scoring normally -- only an explicit `true` counts as
    confusion, and "I don't know" is still an answer;
  * a confused answer is held back and the question explained, at most once;
  * a confused answer that is kept anyway is never scored as evidence.
"""

from __future__ import annotations

from app.api.v1.diagnosis.advisor import AnswerInsight, LLMNextQuestionAdvisor
from app.api.v1.diagnosis.service import (
    _CLARIFY_FALLBACK,
    _REPROMPT,
    needs_fallback_score,
    reprompt_for,
    score_kept_confusion,
    should_discard_as_unresponsive,
)


def _parse(payload: str) -> AnswerInsight | None:
    return LLMNextQuestionAdvisor(provider=None)._parse(payload)


# --- the parser -------------------------------------------------------------

def test_confused_defaults_false_when_the_field_is_absent():
    insight = _parse('{"score_label":"red","responsive":true}')
    assert insight.confused is False
    assert insight.clarification is None


def test_only_an_explicit_true_counts_as_confusion():
    for value in ('"true"', '"yes"', "1", "null", '""', "false"):
        insight = _parse('{"score_label":"red","confused":%s}' % value)
        assert insight.confused is False, value
    assert _parse('{"score_label":"red","confused":true}').confused is True


def test_the_clarification_is_kept_only_for_a_confused_answer():
    """A stray clarification on an ordinary answer must never reach the founder."""
    insight = _parse(
        '{"score_label":"green","confused":false,"clarification":"Put simply..."}'
    )
    assert insight.clarification is None


def test_the_clarification_is_whitespace_normalised():
    insight = _parse(
        '{"score_label":"red","confused":true,'
        '"clarification":"  No problem.\\n\\nPut simply:   who pays you?  "}'
    )
    assert insight.clarification == "No problem. Put simply: who pays you?"


def test_an_unusable_clarification_is_dropped():
    long_text = "x" * 601
    for raw in ('""', "42", "null", '"%s"' % long_text, '["a"]'):
        insight = _parse('{"score_label":"red","confused":true,"clarification":%s}' % raw)
        assert insight.confused is True
        assert insight.clarification is None, raw


# --- the prompt states the rule ---------------------------------------------

def test_the_prompt_separates_confusion_from_not_knowing():
    """The regression to guard is the model treating "I don't know" as
    confusion. That would hold back the single most informative kind of answer
    the diagnosis gets and re-ask it until the founder invents something."""
    advisor = LLMNextQuestionAdvisor(provider=None)

    class _Q:
        question_id, category, question_text = 1, "Sales", "What is your CAC?"

    system = advisor._build_request(_Q(), "What is CAC?", [_Q()], []).messages[0].content
    assert "confused" in system
    assert "clarification" in system
    assert "\"I don't know\"" in system
    assert "never give an example" in system.lower()


# --- the gate ---------------------------------------------------------------

def _confused(clarification: str | None = "Put simply: who pays you?") -> AnswerInsight:
    return AnswerInsight(
        "red", 0.9, 7, "", responsive=True, confused=True, clarification=clarification,
    )


def test_a_confused_answer_is_held_back_once():
    assert should_discard_as_unresponsive(
        _confused(), created_here=True, already_reprompted=False) is True


def test_confusion_shares_the_once_per_question_bound():
    """A model that keeps reading confusion must not trap the founder."""
    assert should_discard_as_unresponsive(
        _confused(), created_here=True, already_reprompted=True) is False


def test_only_this_request_s_own_insert_is_discarded():
    assert should_discard_as_unresponsive(
        _confused(), created_here=False, already_reprompted=False) is False


# --- what Ally says back ------------------------------------------------------

def test_a_confused_founder_gets_the_question_explained():
    assert reprompt_for(_confused()) == "Put simply: who pays you?"


def test_a_confused_founder_without_a_rewording_gets_the_fallback():
    """Never the "you answered a different question" line: that is untrue and
    discouraging said to someone who was honest about being lost."""
    assert reprompt_for(_confused(None)) == _CLARIFY_FALLBACK


def test_an_off_topic_answer_still_gets_the_original_reprompt():
    off_topic = AnswerInsight("red", 0.9, 7, "", responsive=False)
    assert reprompt_for(off_topic) == _REPROMPT
    assert reprompt_for(None) == _REPROMPT


# --- a kept confusion is never evidence --------------------------------------

def test_a_kept_confused_answer_is_not_applicable_not_red():
    """Past the bound the answer is kept, and it must not be scored as a gap.
    NOT_APPLICABLE is excluded from both sides of the pillar score."""
    kept = score_kept_confusion(_confused())
    assert kept.score_label == "not_applicable"
    assert kept.score is None
    # Still counts as scored, so the AMBER fallback does not overwrite it.
    assert needs_fallback_score(kept) is False


def test_ordinary_answers_pass_through_untouched():
    plain = AnswerInsight("red", 0.9, 7, "")
    assert score_kept_confusion(plain) is plain
    assert score_kept_confusion(None) is None
