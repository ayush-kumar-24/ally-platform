"""Config-driven routing + cross-provider failover.

Two ideas live here:

1. LLMRoutingConfig -- routing as *configuration*, not code. A declarative default
   provider + ordered fallback chain + temperature + per-provider reasoning models.
   Buildable from env (today) or a dict/file (tomorrow) without touching code.

2. FailoverLLMProvider -- a composite that ITSELF implements the FROZEN M5
   LLMProvider interface. It tries providers in order (preferring currently-healthy
   ones), moving to the next on failure: OpenAI -> Claude -> Gemini -> Mock. Because
   it satisfies the same interface, M5's AIExecutionService/AIRouter register it as a
   single provider ("auto") and never change. Mock is always the last link, so the
   chain always yields an answer rather than failing closed on transient outages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from app.api.v1.ally.execution.provider import LLMProvider, MockLLMProvider
from app.api.v1.ally.execution.router import AIRouter, RoutingPolicy
from app.api.v1.ally.execution.schemas import (
    ProviderHealth,
    ProviderMetadata,
    ProviderRequest,
    ProviderResponse,
)
from app.api.v1.ally.execution.service import AIExecutionService, build_execution_service
from app.integrations.llm.anthropic_provider import ClaudeProvider
from app.integrations.llm.errors import LLMUnavailableError
from app.integrations.llm.gemini_provider import GeminiProvider
from app.integrations.llm.health import HealthRegistry
from app.integrations.llm.openai_provider import OpenAIProvider
from app.integrations.llm.settings import LLMSettings

_FAILURE_THRESHOLD = 1  # one failure marks a provider unhealthy (still retried last)


# --------------------------------------------------------------------------- #
# Routing configuration                                                        #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LLMRoutingConfig:
    """The routing shape. Credentials/models/URLs stay in LLMSettings (env); this is
    the *policy* -- which provider leads, who backs it up, and at what temperature."""

    default_provider: str = "mock"
    fallback: tuple[str, ...] = ()
    temperature: Decimal = Decimal("0.7")
    reasoning_models: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: LLMSettings) -> "LLMRoutingConfig":
        return cls(
            default_provider=settings.provider,
            fallback=tuple(settings.fallback),
            temperature=Decimal(str(settings.temperature)),
            reasoning_models=dict(settings.reasoning_models),
        )

    @classmethod
    def from_dict(cls, data: Mapping) -> "LLMRoutingConfig":
        """Load from a plain mapping (JSON/YAML config). Keys never live here --
        only routing shape. Accepts `provider` or `default_provider`."""
        return cls(
            default_provider=str(data.get("provider") or data.get("default_provider") or "mock").lower(),
            fallback=tuple(str(x).lower() for x in data.get("fallback", ())),
            temperature=Decimal(str(data.get("temperature", "0.7"))),
            reasoning_models=dict(data.get("reasoning_models") or data.get("reasoning_model") or {}),
        )


# --------------------------------------------------------------------------- #
# Failover provider                                                            #
# --------------------------------------------------------------------------- #


class FailoverLLMProvider(LLMProvider):
    """Ordered provider chain with health-aware failover. Implements LLMProvider so
    M5 sees one provider. Prefers healthy providers but always retries all (so an
    unhealthy provider can recover); returns the first success, raises only if every
    provider fails."""

    def __init__(self, chain: list[tuple[str, LLMProvider]], registry: HealthRegistry):
        if not chain:
            raise ValueError("FailoverLLMProvider requires at least one provider")
        self._chain = chain
        self._registry = registry

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        last_exc: Exception | None = None
        for _name, provider in self._ordered():
            try:
                return provider.generate(request)  # provider records its own health
            except Exception as exc:               # noqa: BLE001 -- try the next link
                last_exc = exc
                continue
        raise last_exc or LLMUnavailableError("failover: all providers exhausted")

    def health(self) -> ProviderHealth:
        healthy = [n for n, _ in self._chain if self._is_healthy(n)]
        return ProviderHealth(
            healthy=bool(healthy),
            detail=f"failover healthy via {healthy}" if healthy else "failover: all providers unhealthy",
        )

    def metadata(self) -> ProviderMetadata:
        models: list[str] = []
        for _n, p in self._chain:
            models.extend(p.metadata().models)
        return ProviderMetadata(name="auto", models=tuple(dict.fromkeys(models)), supports_json=True)

    def health_snapshot(self) -> dict[str, dict]:
        return self._registry.snapshot()

    # --- internals --------------------------------------------------------

    def _ordered(self) -> list[tuple[str, LLMProvider]]:
        # Stable sort: currently-healthy providers first, configured order preserved.
        return sorted(self._chain, key=lambda item: (not self._is_healthy(item[0])))

    def _is_healthy(self, name: str) -> bool:
        state = self._registry.get(name)
        return state.healthy if state else True


# --------------------------------------------------------------------------- #
# Assembly                                                                      #
# --------------------------------------------------------------------------- #

_PROVIDER_FACTORIES = {
    "openai": lambda s, hs: OpenAIProvider(
        api_key=s.openai_api_key, model=s.openai_model, base_url=s.openai_base_url,
        timeout=s.timeout, health_state=hs),
    "anthropic": lambda s, hs: ClaudeProvider(
        api_key=s.anthropic_api_key, model=s.anthropic_model, base_url=s.anthropic_base_url,
        timeout=s.timeout, health_state=hs),
    "gemini": lambda s, hs: GeminiProvider(
        api_key=s.gemini_api_key, model=s.gemini_model, base_url=s.gemini_base_url,
        timeout=s.timeout, health_state=hs),
}
_KEYS = {
    "openai": lambda s: s.openai_api_key,
    "anthropic": lambda s: s.anthropic_api_key,
    "gemini": lambda s: s.gemini_api_key,
}
_MODELS = {
    "openai": lambda s: s.openai_model,
    "anthropic": lambda s: s.anthropic_model,
    "gemini": lambda s: s.gemini_model,
    "mock": lambda s: "mock-standard",
}


def build_provider_registry(settings: LLMSettings, registry: HealthRegistry) -> dict[str, LLMProvider]:
    """Instantiate mock (always) + every provider with an API key, each wired to a
    shared health state so failover ordering can read live health."""
    providers: dict[str, LLMProvider] = {"mock": MockLLMProvider()}
    registry.ensure("mock", "mock-standard", failure_threshold=_FAILURE_THRESHOLD)
    for name, factory in _PROVIDER_FACTORIES.items():
        if _KEYS[name](settings):
            state = registry.ensure(name, _MODELS[name](settings), failure_threshold=_FAILURE_THRESHOLD)
            providers[name] = factory(settings, state)
    return providers


def _resolve_chain(config: LLMRoutingConfig, providers: Mapping[str, LLMProvider]) -> list[str]:
    """Ordered, de-duplicated chain of AVAILABLE providers, with mock always last."""
    ordered = [config.default_provider, *config.fallback, "mock"]
    seen: set[str] = set()
    chain = [n for n in ordered if n in providers and not (n in seen or seen.add(n))]
    return chain or ["mock"]


def build_failover_execution(
    settings: LLMSettings | None = None,
    config: LLMRoutingConfig | None = None,
) -> AIExecutionService:
    """Assemble the settings/config-driven failover execution service.

    Env keys -> providers; LLMRoutingConfig -> the ordered chain. The failover is
    registered as "auto"; the AIRouter (used unchanged) routes to it. Each provider
    calls its own model, so the chain can span vendors under a single RoutingDecision.
    """
    settings = settings or LLMSettings()
    config = config or LLMRoutingConfig.from_settings(settings)

    registry = HealthRegistry()
    providers = build_provider_registry(settings, registry)
    chain_names = _resolve_chain(config, providers)
    chain = [(n, providers[n]) for n in chain_names]
    failover = FailoverLLMProvider(chain, registry)

    primary_model = _MODELS.get(chain_names[0], _MODELS["mock"])(settings)
    router = AIRouter(RoutingPolicy(
        default_provider="auto",
        default_model=primary_model,
        distress_model=primary_model,
        default_temperature=config.temperature,
    ))
    registry_map: dict[str, LLMProvider] = {"auto": failover, **providers}
    return build_execution_service(registry_map, router=router, max_retries=settings.max_retries)
