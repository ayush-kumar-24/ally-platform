"""Reasoning-tier routing -- hermetic. No DB, no network.

Covers needs_reasoning() (the deterministic gate deciding whether a chat turn
routes to the reasoning-tier model) and AIRouter.route()'s precedence between
distress, reasoning, and the default provider.
"""

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

from app.ai_chat.execution.reasoning_classifier import needs_reasoning
from app.api.v1.ally.execution.router import AIRouter, RoutingPolicy
from app.api.v1.ally.execution.schemas import AIRequest


# --- needs_reasoning ----------------------------------------------------------

def _ctx(has_diagnosis):
    return SimpleNamespace(has_diagnosis=has_diagnosis)


def _window(retrieval_empty=True):
    retrieval = SimpleNamespace(is_empty=retrieval_empty)
    return SimpleNamespace(retrieval=retrieval)


def test_no_grounded_data_never_routes_to_reasoning():
    # Question-shaped message, but nothing to reason over -- stays cheap.
    assert needs_reasoning("Why do my demos keep stalling?", _ctx(False), _window(True)) is False


def test_diagnosis_present_but_small_talk_stays_cheap():
    assert needs_reasoning("thanks!", _ctx(True), _window(True)) is False
    assert needs_reasoning("ok", _ctx(True), _window(True)) is False


def test_diagnosis_present_and_question_routes_to_reasoning():
    assert needs_reasoning("Why do my demos keep stalling after the call?", _ctx(True), _window(True)) is True


def test_retrieval_hits_alone_are_enough_grounding():
    assert needs_reasoning("What should I check first?", _ctx(False), _window(retrieval_empty=False)) is True


def test_retrieval_injected_but_empty_is_not_grounding():
    # window.retrieval can be non-None with zero items on a fail-open degrade --
    # that must not count as "we have something to reason over".
    assert needs_reasoning("Why is this happening?", _ctx(False), _window(retrieval_empty=True)) is False


def test_signal_word_without_question_mark_still_routes():
    assert needs_reasoning("help me improve my sales process", _ctx(True), _window(True)) is True


def test_short_message_never_routes_even_with_grounding():
    assert needs_reasoning("why", _ctx(True), _window(True)) is False  # too short to be substantive


def test_empty_or_none_message_is_safe():
    assert needs_reasoning("", _ctx(True), _window(True)) is False
    assert needs_reasoning(None, _ctx(True), _window(True)) is False


# --- AIRouter precedence --------------------------------------------------------

@dataclass(frozen=True)
class FakePrompt:
    distress_mode: bool = False


def _policy():
    return RoutingPolicy(
        default_provider="auto", default_model="gpt-5.4-nano",
        distress_model="mock-careful",
        reasoning_provider="anthropic", reasoning_model="claude-sonnet-5",
    )


def test_reasoning_required_routes_to_reasoning_provider_and_model():
    router = AIRouter(_policy())
    decision = router.route(AIRequest(prompt=FakePrompt(distress_mode=False), reasoning_required=True))
    assert decision.provider == "anthropic"
    assert decision.model == "claude-sonnet-5"


def test_no_reasoning_required_routes_to_default():
    router = AIRouter(_policy())
    decision = router.route(AIRequest(prompt=FakePrompt(distress_mode=False), reasoning_required=False))
    assert decision.provider == "auto"
    assert decision.model == "gpt-5.4-nano"


def test_distress_wins_over_reasoning():
    router = AIRouter(_policy())
    decision = router.route(AIRequest(prompt=FakePrompt(distress_mode=True), reasoning_required=True))
    assert decision.model == "mock-careful"
    # Distress does not touch provider (matches the pre-existing distress
    # behaviour: only the model swaps, provider stays "auto" for its failover
    # safety net) -- and reasoning is explicitly suppressed by distress too.
    assert decision.provider == "auto"


def test_explicit_override_still_wins_over_reasoning():
    router = AIRouter(_policy())
    decision = router.route(AIRequest(
        prompt=FakePrompt(distress_mode=False), reasoning_required=True,
        requested_provider="mock", requested_model="mock-standard",
    ))
    assert decision.provider == "mock" and decision.model == "mock-standard"


def test_reasoning_unavailable_degrades_to_default_gracefully():
    # A deployment with no anthropic key configures reasoning_provider="auto"
    # (see build_failover_execution) -- reasoning_required then becomes a
    # silent no-op rather than an error.
    policy = RoutingPolicy(default_provider="auto", default_model="gpt-5.4-nano",
                           reasoning_provider="auto", reasoning_model="gpt-5.4-nano")
    router = AIRouter(policy)
    decision = router.route(AIRequest(prompt=FakePrompt(distress_mode=False), reasoning_required=True))
    assert decision.provider == "auto" and decision.model == "gpt-5.4-nano"
