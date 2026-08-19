"""A diagnosis answer has to answer the question that was asked.

The Founder DNA phase has gated this since 2026-08-19; the diagnosis phase did
not, and the gap was measurable. A scripted answer about time allocation landed
on "Think of the last time you faced real uncertainty outside of work", was
correctly scored Red for containing no evidence, and two such Reds on
distress-tagged questions flipped the entire report into the distress variant --
opening a steady founder's report with "what you are carrying right now matters
more than any diagnosis". The score was a measurement of nothing, and everything
downstream (risk model, root causes, pillar bands, distress trigger) consumed it
as if it were real.

The verdict rides on the advisor call the phase ALREADY makes for every answer,
so this costs no extra LLM call and no extra latency. That is the whole reason
it is judged by the model here rather than by the deterministic rules the
Founder DNA phase uses: those catch an echo or a keyboard mash, and this failure
was neither -- it was a well-formed answer to a different question.

Two properties matter more than the mechanism, and both are pinned below:
  * it fails OPEN everywhere -- no advisor, a failed call, an unparseable reply,
    or a model that has never heard of the field all leave the answer standing;
  * it judges TOPIC, not quality -- "I don't know" is an answer, and a poor
    answer is what score_label is for.
"""

from __future__ import annotations

from app.api.v1.diagnosis.advisor import AnswerInsight, LLMNextQuestionAdvisor


def _parse(payload: str) -> AnswerInsight | None:
    return LLMNextQuestionAdvisor.__dict__["_parse"](
        LLMNextQuestionAdvisor(provider=None), payload
    )


# --- the parser fails open --------------------------------------------------

def test_responsive_defaults_true_when_the_field_is_absent():
    """An older prompt, a model that ignores the field, a truncated reply. None
    of those are evidence the founder wrote something irrelevant."""
    insight = _parse('{"score_label":"amber","confidence":0.7,"next_question_id":3}')
    assert insight is not None
    assert insight.responsive is True


def test_only_an_explicit_false_rejects():
    assert _parse('{"score_label":"red","responsive":false}').responsive is False
    assert _parse('{"score_label":"red","responsive":true}').responsive is True


def test_a_non_boolean_responsive_is_treated_as_true():
    """Guards the shape of the check itself: `is not False` must not be written
    as a truthiness test, or the string "false" -- which is truthy -- would read
    as responsive while the string "no" would too, inconsistently."""
    for value in ('"false"', '"no"', "0", "null", '""'):
        insight = _parse('{"score_label":"red","responsive":%s}' % value)
        assert insight.responsive is True, value


def test_the_dataclass_default_is_responsive():
    """Every construction site that predates this field keeps working, and keeps
    working in the safe direction."""
    assert AnswerInsight("green", 1.0, 1, "").responsive is True


# --- the verdict does not disturb scoring -----------------------------------

def test_responsiveness_is_independent_of_score_label():
    """Topic and quality are separate axes. A responsive answer can still be Red
    (that is the common case -- an honest "I have never measured this"), and the
    gate must not turn score_label into a proxy for relevance."""
    insight = _parse('{"score_label":"red","responsive":true}')
    assert insight.responsive is True
    assert insight.score_label == "red"
    assert insight.score == 2  # risk scale: red is worst


# --- the prompt states the rule it is judged on -----------------------------

def test_the_prompt_tells_the_model_to_judge_topic_not_quality():
    """The single most likely way this regresses is a prompt edit that lets the
    model reject weak answers. A founder admitting they have never measured
    something is exactly the signal the diagnosis exists to capture; rejecting
    it would delete the finding and re-ask until they invent one."""
    advisor = LLMNextQuestionAdvisor(provider=None)

    class _Q:
        question_id, category, question_text = 1, "Sales", "What is your revenue?"

    request = advisor._build_request(_Q(), "Not much yet.", [_Q()], [])
    system = request.messages[0].content

    assert "responsive" in system
    assert "TOPIC ONLY" in system
    assert "when in doubt, true" in system.lower()
    assert "don't know" in system
