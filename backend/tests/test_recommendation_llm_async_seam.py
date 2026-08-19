"""The LLM recommendation fallback must survive being called from async code.

`LLMRecommendationFallback.fill` is sync, but the only thing that calls it --
`ReasoningService._run_pipeline` -- is `async def`. So by the time `fill` runs,
this thread already has a running event loop.

That combination shipped broken: `_ask` drove the provider with a bare
`asyncio.run`, which raises "cannot be called from a running event loop" when a
loop is already up. The RuntimeError fell outside `fill`'s narrow except tuple,
escaped the module's documented fail-open contract, and rolled back the entire
reasoning transaction -- a completed 30-answer diagnosis persisted zero
founder_reports and the founder was shown "your diagnosis hasn't run yet".

The same seam had already been fixed once in ReasoningTrigger; this file exists
so the next person cannot reintroduce it here.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest

from app.api.v1.reasoning.engines.recommendation_llm import LLMRecommendationFallback
from app.api.v1.reasoning.schemas import RecommendationType, ScoredRootCause
from app.models.enums import ConfirmationStatus
from app.services.llm.base import LLMError


def _scored(rank: int = 1) -> ScoredRootCause:
    return ScoredRootCause(
        root_cause_id=42,
        category_risk_score=Decimal("0.60"),
        confirmation_status=ConfirmationStatus.CONFIRMED,
        confirmation_multiplier=Decimal("1.0"),
        stage_probability=Decimal("0.50"),
        industry_probability=Decimal("0.50"),
        final_weighted_score=Decimal("0.72"),
        rank=rank,
        is_top_finding=True,
    )


class _Provider:
    """Minimal async LLM provider returning one usable recommendation."""

    def __init__(self, payload=None, error: Exception | None = None):
        self._payload = payload if payload is not None else {
            "rationale": "Buyers stall because nobody owns the handoff.",
            "next_actions": ["Map the handoff", "Name one owner"],
        }
        self._error = error
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        if self._error is not None:
            raise self._error

        class _R:
            text = json.dumps(self._payload)

        return _R()


UNCOVERED = [("RC-1", _scored(), "No Buyer Journey Mapping")]


def test_fill_works_when_a_loop_is_already_running():
    """The regression itself: fill() called from inside a live event loop.

    Before the fix this raised RuntimeError instead of returning anything.
    """
    provider = _Provider()
    fallback = LLMRecommendationFallback(provider)

    async def _driver():
        # Exactly the situation _run_pipeline creates: sync fill() invoked while
        # this thread owns a running loop.
        return fallback.fill(UNCOVERED, stage_name="Seed", industry="SaaS")

    out = asyncio.run(_driver())

    assert provider.calls == 1
    assert len(out) == 1
    assert out[0].source == "llm"
    assert out[0].intervention_id == 0
    assert out[0].recommendation_type is RecommendationType.SOLVE
    assert out[0].next_actions == ("Map the handoff", "Name one owner")


def test_fill_still_works_with_no_loop_running():
    """The plain sync path must keep working -- run_sync handles both."""
    provider = _Provider()
    out = LLMRecommendationFallback(provider).fill(UNCOVERED)

    assert provider.calls == 1
    assert len(out) == 1


@pytest.mark.parametrize(
    "boom",
    [
        LLMError("provider exploded"),
        RuntimeError("event loop weirdness"),
        ValueError("garbage"),
        KeyError("missing"),
    ],
    ids=["llm-error", "runtime-error", "value-error", "key-error"],
)
def test_fill_fails_open_on_any_provider_error(boom):
    """The module contract is 'a diagnosis is never blocked on a library gap'.

    RuntimeError is in this list deliberately: it is the class of failure that
    voided real founders' reports, and a narrow except tuple is what let it out.
    """
    provider = _Provider(error=boom)

    async def _driver():
        return LLMRecommendationFallback(provider).fill(UNCOVERED)

    # Fails open in both worlds -- loop running and not.
    assert asyncio.run(_driver()) == ()
    assert LLMRecommendationFallback(_Provider(error=boom)).fill(UNCOVERED) == ()


def test_unusable_reply_is_dropped_rather_than_half_reported():
    """A rationale with no actions is a paragraph the founder cannot act on."""
    provider = _Provider(payload={"rationale": "Something is wrong.", "next_actions": []})

    assert LLMRecommendationFallback(provider).fill(UNCOVERED) == ()
