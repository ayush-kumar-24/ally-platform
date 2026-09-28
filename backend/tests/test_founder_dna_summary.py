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


# --- the cache, and the call it stopped repeating ---------------------------
#
# ensure_dna_summaries had no test at all, which is how a synchronous LLM call
# on every single view of a page went unnoticed.

class _Session:
    """Just enough Session for ensure_dna_summaries: it only commits."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Report:
    def __init__(self, founder_dna):
        self.founder_id = 1
        self.report_id = 1
        self.founder_dna = founder_dna


def _run(monkeypatch, report, produced, *, calls):
    """Run ensure_dna_summaries with the provider and summariser stubbed."""
    from app.api.v1.reports import dna_summaries as mod

    monkeypatch.setattr(mod.settings, "FOUNDER_DNA_SUMMARY_LLM", True, raising=False)
    monkeypatch.setattr(mod, "provider_for_task", lambda *a, **k: object())

    def _summarise(_provider, dimensions):
        calls.append(sorted(dimensions))
        return {c: b for c, b in produced.items() if c in dimensions}

    monkeypatch.setattr(mod, "summarise_dimensions", _summarise)
    mod.ensure_dna_summaries(_Session(), report)


def test_a_dimension_the_model_declines_is_not_asked_about_again(monkeypatch):
    """The bug: "Monday." and "The bridge" cannot be summarised and never will
    be, so leaving them out of the cache re-ran a 25-second-timeout LLM call on
    every view of that founder's Founder DNA page, forever."""
    report = _Report({"core_values": ["a real paragraph"], "focus_attention": ["Monday."]})
    calls = []

    _run(monkeypatch, report, {"core_values": ["Pulled a batch over seal strength"]},
         calls=calls)
    assert calls == [["core_values", "focus_attention"]]

    summaries = report.founder_dna["_summaries"]
    assert summaries["core_values"] == ["Pulled a batch over seal strength"]
    assert summaries["focus_attention"] == []          # attempted, nothing to say

    # Second view: nothing left to ask about.
    _run(monkeypatch, report, {"core_values": ["x"]}, calls=calls)
    assert len(calls) == 1, "the declined dimension was re-sent"


def test_a_total_failure_still_retries_on_the_next_view(monkeypatch):
    """A timeout or a missing provider also yields {}. Marking every dimension
    attempted off one blip would disable this founder's summaries for good."""
    report = _Report({"core_values": ["a real paragraph"]})
    calls = []

    _run(monkeypatch, report, {}, calls=calls)
    assert "_summaries" not in report.founder_dna

    _run(monkeypatch, report, {"core_values": ["got there in the end"]}, calls=calls)
    assert len(calls) == 2
    assert report.founder_dna["_summaries"]["core_values"] == ["got there in the end"]


def test_an_empty_summary_is_never_offered_as_a_summary(monkeypatch):
    """The stored empty list marks the dimension attempted. It must not reach
    the report AS a summary -- the card falls back to the founder's own words,
    which is what payload.dimension_summaries' falsy filter already does."""
    report = _Report({"core_values": ["a real paragraph"], "focus_attention": ["Monday."]})
    _run(monkeypatch, report, {"core_values": ["Pulled a batch"]}, calls=[])

    stored = report.founder_dna["_summaries"]
    assert stored["focus_attention"] == []
    # The same filter payload.py applies when it builds dimension_summaries.
    assert {c: tuple(b) for c, b in stored.items() if b} == {
        "core_values": ("Pulled a batch",)
    }


# --- what the endpoint reads back, and what it no longer waits for ----------

def test_only_non_empty_previews_are_offered_to_the_page():
    """An attempted-but-unsummarised dimension is stored as [] so it is not
    re-sent. It must not travel to the page as a preview -- the card renders
    the founder's own answer instead."""
    from app.api.v1.reports.dna_summaries import current_summaries

    report = _Report({
        "core_values": ["a real paragraph"],
        "focus_attention": ["Monday."],
        "_summaries": {"core_values": ["Pulled a batch"], "focus_attention": []},
    })
    assert current_summaries(report) == {"core_values": ["Pulled a batch"]}


def test_nothing_is_scheduled_once_every_dimension_has_been_attempted(monkeypatch):
    """The endpoint asks this before scheduling the background fill. It was the
    7.7s and 10.1s on the request path, twice in one page load."""
    from app.api.v1.reports import dna_summaries as mod

    monkeypatch.setattr(mod.settings, "FOUNDER_DNA_SUMMARY_LLM", True, raising=False)

    done = _Report({
        "core_values": ["a real paragraph"],
        "focus_attention": ["Monday."],
        "_summaries": {"core_values": ["Pulled a batch"], "focus_attention": []},
    })
    assert mod.pending_dimensions(done) == {}

    fresh = _Report({"core_values": ["a real paragraph"]})
    assert mod.pending_dimensions(fresh) == {"core_values": ["a real paragraph"]}


def test_the_feature_flag_off_schedules_nothing(monkeypatch):
    from app.api.v1.reports import dna_summaries as mod

    monkeypatch.setattr(mod.settings, "FOUNDER_DNA_SUMMARY_LLM", False, raising=False)
    assert mod.pending_dimensions(_Report({"core_values": ["a real paragraph"]})) == {}


# --- the read on each card, and the card that is not printed ----------------
#
# The card's heading promises a read on the founder; the summariser is told
# never to diagnose, so it could only ever produce a tidier quote. A founder
# asked, about a card headed EMOTIONAL INTELLIGENCE holding "Our Halol plant
# head, Ramesh, 2022": "what can we understand from this sentence about a
# person's emotional intelligence?" Nothing, was the honest answer.

def test_a_read_is_written_from_the_question_and_the_answer(monkeypatch):
    from app.api.v1.reasoning.engines import founder_dna_reads as mod

    captured = {}

    def _fake(provider, request, timeout):
        captured["body"] = request.messages[1].content
        return '{"core_values": "You mind more about the promise than the quarter."}'

    monkeypatch.setattr(mod, "run_sync", lambda coro: coro)
    monkeypatch.setattr(mod, "_generate",
                        lambda p, r, t: _fake(p, r, t))
    out = mod.read_dimensions(object(), {
        "core_values": {"question": "Tell me about a line someone crossed.",
                        "answers": ["A sales manager gave 9% away without asking."]},
    })
    assert out == {"core_values": "You mind more about the promise than the quarter."}
    # The QUESTION must be in the prompt. Without it "The bridge" is a noun,
    # which is how two unrelated founders both previewed as "The bridge".
    assert "Tell me about a line someone crossed." in captured["body"]
    assert "A sales manager gave 9% away" in captured["body"]


def test_a_facet_the_model_leaves_out_has_no_read(monkeypatch):
    """Which is the whole safety of this: it may say nothing rather than
    invent a founder from "Our Halol plant head, Ramesh, 2022."."""
    from app.api.v1.reasoning.engines import founder_dna_reads as mod

    monkeypatch.setattr(mod, "run_sync", lambda coro: coro)
    monkeypatch.setattr(mod, "_generate", lambda p, r, t: '{}')
    assert mod.read_dimensions(object(), {
        "emotional_intelligence": {"question": "When did you misread someone?",
                                   "answers": ["Our Halol plant head, Ramesh, 2022."]},
    }) == {}


def test_a_read_for_a_facet_we_did_not_ask_about_is_dropped(monkeypatch):
    """It would render as a card of its own on the frontend's generic grid."""
    from app.api.v1.reasoning.engines import founder_dna_reads as mod

    monkeypatch.setattr(mod, "run_sync", lambda coro: coro)
    monkeypatch.setattr(mod, "_generate",
                        lambda p, r, t: '{"core_values": "ok", "invented": "no"}')
    out = mod.read_dimensions(object(), {
        "core_values": {"question": "q", "answers": ["a"]}})
    assert out == {"core_values": "ok"}


def test_a_provider_failure_yields_no_reads_rather_than_raising(monkeypatch):
    from app.api.v1.reasoning.engines import founder_dna_reads as mod

    def _boom(coro):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(mod, "run_sync", _boom)
    assert mod.read_dimensions(object(), {
        "core_values": {"question": "q", "answers": ["a"]}}) == {}


def test_origin_and_vision_are_readable_even_though_they_are_strings():
    """`_dimensions` skips them because the summariser only handles lists. A
    read has to cover them -- "Origin: 2013." is the card a founder pointed at
    first."""
    from app.api.v1.reports.dna_summaries import _dimensions, _readable_dimensions

    founder_dna = {"origin": "2013.", "vision": "That customers still trust us.",
                   "core_values": ["a real paragraph"], "archetype": {"x": 1}}
    assert "origin" not in _dimensions(founder_dna)
    readable = _readable_dimensions(founder_dna)
    assert readable["origin"] == ["2013."]
    assert readable["vision"] == ["That customers still trust us."]
    assert "archetype" not in readable, "a structured finding is not a quoted answer"


def test_a_declined_read_is_recorded_so_it_is_not_asked_again(monkeypatch):
    from app.api.v1.reports import dna_summaries as mod

    monkeypatch.setattr(mod.settings, "FOUNDER_DNA_READS_LLM", True, raising=False)
    monkeypatch.setattr(mod, "provider_for_task", lambda *a, **k: object())

    report = _Report({
        "core_values": ["a real paragraph"],
        "emotional_intelligence": ["Our Halol plant head, Ramesh, 2022."],
        "_questions": {"core_values": ["q1"], "emotional_intelligence": ["q2"]},
    })
    calls = []

    def _reads(_provider, items):
        calls.append(sorted(items))
        return {"core_values": "You mind more about the promise."}

    monkeypatch.setattr(mod, "read_dimensions", _reads)
    mod.ensure_dna_reads(_Session(), report)

    stored = report.founder_dna["_reads"]
    assert stored["core_values"] == "You mind more about the promise."
    assert stored["emotional_intelligence"] == "", "declined, and recorded as such"

    mod.ensure_dna_reads(_Session(), report)
    assert len(calls) == 1, "the declined facet was asked about again"


def test_a_total_failure_still_retries(monkeypatch):
    from app.api.v1.reports import dna_summaries as mod

    monkeypatch.setattr(mod.settings, "FOUNDER_DNA_READS_LLM", True, raising=False)
    monkeypatch.setattr(mod, "provider_for_task", lambda *a, **k: object())
    monkeypatch.setattr(mod, "read_dimensions", lambda p, i: {})

    report = _Report({"core_values": ["a real paragraph"]})
    mod.ensure_dna_reads(_Session(), report)
    assert "_reads" not in report.founder_dna
