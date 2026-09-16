"""The Founder DNA card previews: what the model is allowed to come back with.

The interesting cases here are all refusals. A summary that is merely poor costs
a founder some scrolling; a summary that asserts something they never said, or
invents a dimension they were never asked about, is the product putting words in
their mouth on a page titled "your profile". So the parser is permissive about
the envelope and strict about the content, and these tests are mostly about the
second half.
"""

from __future__ import annotations

from app.api.v1.reasoning.engines.founder_dna_summary import (
    _parse,
    _prompt,
    summarise_dimensions,
)
from app.api.v1.reports.dna_summaries import _dimensions

ALLOWED = {"core_values", "decision_style"}


# --- the parser -------------------------------------------------------------

def test_plain_json_is_accepted():
    reply = '{"core_values": ["Refused to ship a dark pattern", "Asked off the project"]}'
    assert _parse(reply, ALLOWED) == {
        "core_values": ["Refused to ship a dark pattern", "Asked off the project"]
    }


def test_json_wrapped_in_prose_or_a_code_fence_is_still_read():
    reply = 'Sure!\n```json\n{"decision_style": ["Calls customers before deciding"]}\n```'
    assert _parse(reply, ALLOWED) == {"decision_style": ["Calls customers before deciding"]}


def test_an_unknown_dimension_is_dropped():
    """The shape a hallucinated dimension arrives in."""
    reply = '{"core_values": ["Told straight"], "risk_appetite": ["Bold"]}'
    assert _parse(reply, ALLOWED) == {"core_values": ["Told straight"]}


def test_leading_bullet_characters_are_stripped():
    reply = '{"core_values": ["- Told straight", "\\u2022 Pushed back once"]}'
    assert _parse(reply, ALLOWED) == {"core_values": ["Told straight", "Pushed back once"]}


def test_more_than_three_bullets_is_cut_to_three():
    reply = '{"core_values": ["a", "b", "c", "d", "e"]}'
    assert _parse(reply, ALLOWED) == {"core_values": ["a", "b", "c"]}


def test_a_bullet_that_is_the_paragraph_again_is_truncated():
    reply = '{"core_values": ["%s"]}' % ("word " * 200)
    assert len(_parse(reply, ALLOWED)["core_values"][0]) <= 120


def test_empty_and_blank_bullets_are_dropped_with_their_dimension():
    reply = '{"core_values": ["", "   "], "decision_style": ["Real one"]}'
    assert _parse(reply, ALLOWED) == {"decision_style": ["Real one"]}


def test_malformed_replies_summarise_to_nothing():
    for reply in ("", "no json here", "{not json}", "[1, 2, 3]", '"a string"'):
        assert _parse(reply, ALLOWED) == {}


# --- the prompt -------------------------------------------------------------

def test_long_answers_are_trimmed_before_they_are_sent():
    body = _prompt({"core_values": ["x" * 5000]})
    assert len(body) < 1500


def test_only_the_first_three_answers_are_sent():
    body = _prompt({"core_values": ["one", "two", "three", "FOURTH"]})
    assert "FOURTH" not in body


def test_blank_answers_leave_no_empty_dimension_in_the_prompt():
    assert _prompt({"core_values": ["", "  "]}) == ""


# --- the call ---------------------------------------------------------------

class _Boom:
    async def generate(self, request):
        raise RuntimeError("provider is down")


class _Reply:
    def __init__(self, text):
        self._text = text

    async def generate(self, request):
        class R:
            text = self._text
        return R()


def test_a_provider_failure_returns_nothing_rather_than_raising():
    """The card falls back to the founder's answers; the page still renders."""
    assert summarise_dimensions(_Boom(), {"core_values": ["Told straight"]}) == {}


def test_nothing_to_summarise_makes_no_call_at_all():
    assert summarise_dimensions(_Boom(), {}) == {}
    assert summarise_dimensions(_Boom(), {"core_values": [""]}) == {}


def test_a_good_reply_comes_back_parsed():
    provider = _Reply('{"core_values": ["Refused to ship a dark pattern"]}')
    assert summarise_dimensions(provider, {"core_values": ["a long answer"]}) == {
        "core_values": ["Refused to ship a dark pattern"]
    }


# --- which keys count as a dimension ---------------------------------------

def test_only_lists_of_answers_are_summarised():
    """archetype is a dict with its own card, origin/vision are single strings
    with theirs, and an already-written summary must not be re-summarised."""
    founder_dna = {
        "core_values": ["one", "two"],
        "stress_response": ["three"],
        "archetype": {"archetype_name": "Operator"},
        "origin": "a single string",
        "vision": "another single string",
        "chronic_state": "Identity Fusion",
        "_summaries": {"core_values": ["already done"]},
        "_origin_text": "bookkeeping",
        "empty": [],
    }
    assert _dimensions(founder_dna) == {
        "core_values": ["one", "two"],
        "stress_response": ["three"],
    }
