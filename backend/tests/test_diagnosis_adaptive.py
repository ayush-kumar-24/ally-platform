"""Adaptive next-question advisor (Hybrid) -- hermetic. No DB, no network.

Covers the pure hybrid decision (`resolve_next`), the LLM response parser, and the
async analyze() fail-open path with a fake provider.
"""

import asyncio
from collections import namedtuple

from app.api.v1.diagnosis.advisor import (
    AnswerInsight,
    LLMNextQuestionAdvisor,
    resolve_next,
)
from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse

Q = namedtuple("Q", "question_id category question_text")

ORDERED = [Q(10, "Founder Psychology", "a"), Q(11, "Product", "b"), Q(12, "Sales", "c")]
SHORTLIST = ORDERED[:2]


# --- resolve_next (pure hybrid decision) ------------------------------------

def test_resolve_next_deterministic_when_no_insight():
    assert resolve_next(ORDERED, SHORTLIST, None) is ORDERED[0]


def test_resolve_next_honours_valid_pick():
    insight = AnswerInsight("red", 0.9, next_question_id=11, rationale="probe")
    assert resolve_next(ORDERED, SHORTLIST, insight).question_id == 11


def test_resolve_next_falls_back_when_pick_outside_shortlist():
    # id 12 is a real candidate but NOT in the shortlist handed to the LLM.
    insight = AnswerInsight("green", 0.8, next_question_id=12, rationale="x")
    assert resolve_next(ORDERED, SHORTLIST, insight) is ORDERED[0]


def test_resolve_next_falls_back_on_null_pick():
    insight = AnswerInsight("amber", 0.5, next_question_id=None, rationale="")
    assert resolve_next(ORDERED, SHORTLIST, insight) is ORDERED[0]


def test_resolve_next_empty_is_none():
    assert resolve_next([], [], None) is None


def test_insight_score_mapping():
    """answers.score carries RISK: green 0, amber 1, red 2. Higher is worse.

    These exact numbers are the scoring schema, not a preference -- they live
    in `scoring_rules` as QUESTION_SCORE_GREEN / _AMBER / _RED (0 / 1 / 2) and
    every reader of answers.score assumes that direction.

    This test previously asserted the inverse (green 2 … red 0), which is how
    the inversion survived: the writer and its test agreed with each other and
    disagreed with every consumer. See test_red_answers_score_worse_than_green
    below for the property that actually matters.
    """
    assert AnswerInsight("green", 1.0, 1, "").score == 0
    assert AnswerInsight("amber", 1.0, 1, "").score == 1
    assert AnswerInsight("red", 1.0, 1, "").score == 2
    assert AnswerInsight(None, 1.0, 1, "").score is None


def test_red_answers_score_worse_than_green():
    """The direction, stated independently of the numbers.

    business_health.py computes `risk_ratio = sum(scores) / (n * 2)` and then
    `health = (1 - risk_ratio) * 100`. If this ordering ever flips again, a
    founder's worst answers produce their best pillar bands -- which is exactly
    what shipped before: 25 red + 5 amber summed to 5 rather than 55 and
    reported 92/100 "Strong" across all six pillars.
    """
    green = AnswerInsight("green", 1.0, 1, "").score
    amber = AnswerInsight("amber", 1.0, 1, "").score
    red = AnswerInsight("red", 1.0, 1, "").score
    assert green < amber < red, "answers.score is a risk scale; red must be highest"

    # And the health inversion downstream must therefore rank them correctly.
    def health(scores):
        return round((1 - sum(scores) / (len(scores) * 2)) * 100)

    assert health([red] * 10) == 0
    assert health([green] * 10) == 100
    assert health([red] * 10) < health([amber] * 10) < health([green] * 10)


# --- parser -----------------------------------------------------------------

def _advisor():
    return LLMNextQuestionAdvisor(provider=None)  # _parse doesn't touch the provider


def test_parse_valid_json():
    ins = _advisor()._parse('{"score_label":"red","confidence":0.9,"next_question_id":11,"rationale":"probe"}')
    assert ins.score_label == "red" and ins.next_question_id == 11 and ins.confidence == 0.9


def test_parse_fenced_and_noisy():
    ins = _advisor()._parse('```json\n{"score_label":"GREEN","next_question_id":"10","confidence":2}\n```')
    assert ins.score_label == "green"          # normalised
    assert ins.next_question_id == 10          # string coerced
    assert ins.confidence == 1.0               # clamped to [0,1]


def test_parse_invalid_label_becomes_none():
    ins = _advisor()._parse('{"score_label":"maybe","next_question_id":11}')
    assert ins.score_label is None and ins.next_question_id == 11


def test_parse_non_json_returns_none():
    assert _advisor()._parse("the model rambled with no json") is None


def test_parse_bad_next_id():
    ins = _advisor()._parse('{"score_label":"amber","next_question_id":"none"}')
    assert ins.next_question_id is None


# --- analyze() fail-open with a fake provider -------------------------------

class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, *, text=None, error=None):
        self._text, self._error = text, error

    async def generate(self, request):
        if self._error is not None:
            raise self._error
        return LLMResponse(text=self._text, model="fake", provider="fake")


def test_analyze_returns_insight():
    adv = LLMNextQuestionAdvisor(
        _FakeProvider(text='{"score_label":"red","confidence":0.7,"next_question_id":11,"rationale":"go deeper"}')
    )
    ins = asyncio.run(adv.analyze(
        answered_question=ORDERED[0], answer_text="we have no customers", shortlist=SHORTLIST, history=[]
    ))
    assert ins.score_label == "red" and ins.next_question_id == 11


def test_analyze_fails_open_on_provider_error():
    adv = LLMNextQuestionAdvisor(_FakeProvider(error=LLMProviderError("boom")))
    ins = asyncio.run(adv.analyze(
        answered_question=ORDERED[0], answer_text="x", shortlist=SHORTLIST, history=[]
    ))
    assert ins is None  # caller will use the deterministic pick


def test_analyze_empty_shortlist_is_none():
    adv = LLMNextQuestionAdvisor(_FakeProvider(text="{}"))
    assert asyncio.run(
        adv.analyze(answered_question=ORDERED[0], answer_text="x", shortlist=[], history=[])
    ) is None
