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
    lower temperature (steadier, safer), and a tighter token budget."""

    default_provider: str = "mock"
    default_model: str = "mock-standard"
    distress_model: str = "mock-careful"
    default_temperature: Decimal = Decimal("0.7")
    distress_temperature: Decimal = Decimal("0.2")
    default_max_tokens: int = 800
    distress_max_tokens: int = 500


class AIRouter:
    def __init__(self, policy: RoutingPolicy | None = None):
        self.policy = policy or RoutingPolicy()

    def route(self, request: AIRequest) -> RoutingDecision:
        p = self.policy
        distress = request.prompt.distress_mode

        provider = request.requested_provider or p.default_provider
        model = request.requested_model or (p.distress_model if distress else p.default_model)
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
