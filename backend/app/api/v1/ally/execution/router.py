"""AIRouter -- decides provider, model, temperature and max_tokens. Nothing else.

It reads routing SIGNALS off the already-built RenderedPrompt (distress mode) and
the caller's optional overrides, then returns a RoutingDecision. It does NOT build
prompts, retrieve, traverse the graph, modify context or compute a diagnosis --
those are other layers. Deterministic: same request + same policy -> same decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.api.v1.ally.execution.schemas import AIRequest, RoutingDecision


@dataclass(frozen=True)
class RoutingPolicy:
    """Provider/model/param policy. Distress routes to a more careful model and a
    lower temperature (steadier, safer), and a tighter token budget.

    reasoning_provider/reasoning_model route a turn that actually needs to
    reason over grounded data (diagnosis, RAG, root causes) to a stronger
    model -- see AIRequest.reasoning_required. Defaults to the mock provider,
    same convention as everything else here: a caller that never sets
    reasoning_required, or a deployment where the reasoning provider isn't
    configured, sees no behaviour change at all."""

    default_provider: str = "mock"
    default_model: str = "mock-standard"
    distress_model: str = "mock-careful"
    default_temperature: Decimal = Decimal("0.7")
    distress_temperature: Decimal = Decimal("0.2")
    default_max_tokens: int = 800
    distress_max_tokens: int = 500
    reasoning_provider: str = "mock"
    reasoning_model: str = "mock-standard"


class AIRouter:
    def __init__(self, policy: RoutingPolicy | None = None):
        self.policy = policy or RoutingPolicy()

    def route(self, request: AIRequest) -> RoutingDecision:
        p = self.policy
        distress = request.prompt.distress_mode
        # Distress wins outright over reasoning-tier routing: wellbeing before
        # a stronger model, same precedence the rest of the pipeline gives it
        # (see reasoning/service.py's own distress-overrides-routing comment).
        reasoning = request.reasoning_required and not distress

        provider = request.requested_provider or (
            p.reasoning_provider if reasoning else p.default_provider
        )
        model = request.requested_model or (
            p.distress_model if distress
            else p.reasoning_model if reasoning
            else p.default_model
        )
        temperature = (
            request.temperature
            if request.temperature is not None
            else (p.distress_temperature if distress else p.default_temperature)
        )
        max_tokens = (
            request.max_tokens
            if request.max_tokens is not None
            else (p.distress_max_tokens if distress else p.default_max_tokens)
        )
        return RoutingDecision(
            provider=provider, model=model, temperature=temperature, max_tokens=max_tokens
        )
