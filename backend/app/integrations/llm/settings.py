"""Environment-driven LLM configuration + provider/router factories.

Reads plain environment variables (no coupling to app settings), builds the
provider registry, and derives an AIRouter RoutingPolicy from them. The AIRouter
class is used unchanged -- it is "extended" only through configuration.

Graceful selection: if the chosen provider has no API key, the default falls back
to "mock", so the system degrades to the offline provider rather than failing.
"""

from __future__ import annotations

import os

from app.api.v1.ally.execution.provider import LLMProvider, MockLLMProvider
from app.api.v1.ally.execution.router import RoutingPolicy
from app.integrations.llm.anthropic_provider import ClaudeProvider
from app.integrations.llm.gemini_provider import GeminiProvider
from app.integrations.llm.openai_provider import OpenAIProvider

_MODELS = {
    "openai": lambda s: s.openai_model,
    "anthropic": lambda s: s.anthropic_model,
    "gemini": lambda s: s.gemini_model,
    "mock": lambda s: "mock-standard",
}


class LLMSettings:
    """Snapshot of the LLM-related environment variables."""

    def __init__(self, env: dict | None = None):
        e = env if env is not None else os.environ
        self.provider = e.get("ALLY_LLM_PROVIDER", "mock").lower()
        self.timeout = float(e.get("ALLY_LLM_TIMEOUT", "30"))
        self.max_retries = int(e.get("ALLY_LLM_MAX_RETRIES", "2"))

        # Routing shape (consumed by LLMRoutingConfig). ALLY_LLM_FALLBACK is a comma
        # list, e.g. "anthropic,gemini"; per-provider reasoning models come from
        # ALLY_REASONING_MODEL_<PROVIDER> (e.g. ALLY_REASONING_MODEL_OPENAI=o4-mini).
        self.fallback = [p.strip().lower() for p in e.get("ALLY_LLM_FALLBACK", "").split(",") if p.strip()]
        self.temperature = float(e.get("ALLY_LLM_TEMPERATURE", "0.7"))
        self.reasoning_models = {
            name: e[f"ALLY_REASONING_MODEL_{name.upper()}"]
            for name in ("openai", "anthropic", "gemini")
            if e.get(f"ALLY_REASONING_MODEL_{name.upper()}")
        }

        self.openai_api_key = e.get("OPENAI_API_KEY")
        self.openai_model = e.get("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_base_url = e.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        self.anthropic_api_key = e.get("ANTHROPIC_API_KEY")
        self.anthropic_model = e.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.anthropic_base_url = e.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        self.gemini_api_key = e.get("GEMINI_API_KEY")
        self.gemini_model = e.get("GEMINI_MODEL", "gemini-1.5-flash")
        self.gemini_base_url = e.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")


def build_providers(settings: LLMSettings) -> dict[str, LLMProvider]:
    """Registry keyed by provider name. Mock is always present; a real provider is
    registered only when its API key is configured."""
    providers: dict[str, LLMProvider] = {"mock": MockLLMProvider()}
    if settings.openai_api_key:
        providers["openai"] = OpenAIProvider(
            api_key=settings.openai_api_key, model=settings.openai_model,
            base_url=settings.openai_base_url, timeout=settings.timeout,
        )
    if settings.anthropic_api_key:
        providers["anthropic"] = ClaudeProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model,
            base_url=settings.anthropic_base_url, timeout=settings.timeout,
        )
    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider(
            api_key=settings.gemini_api_key, model=settings.gemini_model,
            base_url=settings.gemini_base_url, timeout=settings.timeout,
        )
    return providers


def build_routing_policy(settings: LLMSettings, providers: dict[str, LLMProvider]) -> RoutingPolicy:
    """Derive the router policy from settings. Falls back to 'mock' when the
    selected provider is not available."""
    provider = settings.provider if settings.provider in providers else "mock"
    model = _MODELS.get(provider, _MODELS["mock"])(settings)
    return RoutingPolicy(default_provider=provider, default_model=model, distress_model=model)
