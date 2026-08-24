"""The free report's 3+3 plan must have both halves, and curated lines must win.

The framework doc's s6 defines the free tier as "one diagnosed root cause with
a 3+3 action plan (3 lines to confirm/isolate the problem further, 3 lines to
solve it)", and all three of its example reports show both halves filled.

StandardRecommendationEngine cannot produce that: it types a recommendation
SOLVE when its lead supporting cause is CONFIRMED and CONFIRM otherwise, so a
report diagnosing ONE cause -- which is what the free tier is -- gets every
recommendation typed the same way. Reproduced live on goxlally.ai: an
unconfirmed lead cause gave three confirm lines and zero solve lines, with
nothing on the page indicating half the plan was missing.

These pin the balancer that completes it, and in particular the rule that makes
it safe to switch on: a reviewed intervention's line is never dropped, reworded
or reordered, and only the shortfall is authored.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.api.v1.reasoning.engines.action_plan_llm import (
    LINES_PER_SIDE,
    LLMActionPlanBalancer,
)
from app.services.llm.base import LLMError


class _Provider:
    def __init__(self, payload=None, raises=None):
        self._payload = payload
        self._raises = raises
        self.calls = 0
        self.last_prompt = None

    async def generate(self, request):
        self.calls += 1
        self.last_prompt = request.messages[-1].content
        if self._raises is not None:
            raise self._raises
        text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return SimpleNamespace(text=text)


CURATED = ["Count the days spent reading versus talking to a customer."]


def _balance(provider, confirm=None, solve=None, **kw):
    balancer = LLMActionPlanBalancer(provider)
    return balancer.balance(
        CURATED if confirm is None else confirm,
        [] if solve is None else solve,
        root_cause="Conviction gap disguised as an information gap",
        stage_name="Ideation",
        **kw,
    )


# --- the fix -------------------------------------------------------------------

def test_the_empty_half_is_filled():
    """THE REGRESSION: three confirm lines, zero solve lines, shipped as-is."""
    provider = _Provider({
        "confirm": CURATED,
        "solve": ["Give yourself a 7-day deadline.", "Cut reading-only tasks.",
                  "Tell one person the deadline out loud."],
    })
    confirm, solve = _balance(provider)

    assert confirm == CURATED
    assert len(solve) == LINES_PER_SIDE
    assert "Give yourself a 7-day deadline." in solve


def test_a_curated_line_is_never_reworded():
    """The model is told to keep existing lines verbatim, but the merge does not
    depend on it obeying: existing lines are re-read from the input, not from
    the reply, so a quiet edit cannot reach the page."""
    provider = _Provider({
        "confirm": ["Count the days you spent reading rather than talking to a customer."],
        "solve": ["Set a deadline."],
    })
    confirm, _ = _balance(provider)

    assert confirm == CURATED, "the curated line must survive exactly as written"


def test_curated_lines_come_first():
    provider = _Provider({
        "confirm": ["A generated confirm line.", *CURATED],
        "solve": ["Set a deadline."],
    })
    confirm, _ = _balance(provider)

    assert confirm[0] == CURATED[0]


def test_neither_half_exceeds_the_cap():
    provider = _Provider({
        "confirm": CURATED + ["Ask three customers what they nearly bought instead.",
                              "Track which feature drove your last signup.",
                              "List every call you postponed this month.",
                              "Note where each lead first heard of you."],
        "solve": ["Set a go/no-go date for the pilot.",
                  "Stop shipping features nobody requested.",
                  "Hand the weekly report to your co-founder.",
                  "Book three pricing calls before Friday."],
    })
    confirm, solve = _balance(provider)

    assert len(confirm) == LINES_PER_SIDE
    assert len(solve) == LINES_PER_SIDE


def test_a_line_the_model_repeats_is_not_duplicated():
    provider = _Provider({
        "confirm": CURATED,
        "solve": ["Set a deadline.", "Set a deadline.", "Tell someone."],
    })
    _, solve = _balance(provider)

    assert solve == ["Set a deadline.", "Tell someone."]


# --- when it must not run ------------------------------------------------------

def test_a_plan_the_library_already_filled_costs_nothing():
    provider = _Provider({"confirm": ["x"], "solve": ["y"]})
    confirm, solve = _balance(
        provider,
        confirm=[f"Confirm {i}." for i in range(LINES_PER_SIDE)],
        solve=[f"Solve {i}." for i in range(LINES_PER_SIDE)],
    )

    assert provider.calls == 0, "no shortfall, so no call"
    assert len(confirm) == LINES_PER_SIDE and len(solve) == LINES_PER_SIDE


def test_an_empty_plan_is_not_invented_from_nothing():
    """With no curated line on either side there is no diagnosis to build on,
    and authoring both halves would be advice with no evidence behind it."""
    provider = _Provider({"confirm": ["a", "b", "c"], "solve": ["d", "e", "f"]})
    confirm, solve = _balance(provider, confirm=[], solve=[])

    assert (confirm, solve) == ([], [])
    assert provider.calls == 0


def test_blank_lines_do_not_count_as_content():
    provider = _Provider({"confirm": CURATED, "solve": ["Set a deadline."]})
    confirm, _ = _balance(provider, confirm=CURATED + ["   ", ""])
    assert confirm == CURATED


# --- every failure keeps the library's plan ------------------------------------

@pytest.mark.parametrize("provider", [
    _Provider(raises=LLMError("provider down")),
    _Provider(raises=asyncio.TimeoutError()),
    _Provider("not json"),
    _Provider({"confirm": CURATED}),          # solve half missing entirely
    _Provider({"solve": "not a list"}),
    _Provider({}),
])
def test_a_failure_leaves_the_plan_exactly_as_the_library_built_it(provider):
    confirm, solve = _balance(provider)
    assert confirm == CURATED
    assert solve == []


# --- the prompt --------------------------------------------------------------

def test_the_prompt_carries_the_diagnosis_and_the_existing_lines():
    provider = _Provider({"confirm": CURATED, "solve": ["Set a deadline."]})
    _balance(provider, evidence=["I keep saying I need more research."])

    prompt = provider.last_prompt
    assert "Conviction gap disguised as an information gap" in prompt
    assert "Ideation" in prompt
    assert CURATED[0] in prompt
    assert "I keep saying I need more research." in prompt
    assert "(none yet)" in prompt, "the empty half must be shown as empty"
