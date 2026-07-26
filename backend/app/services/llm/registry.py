"""Config-driven registry of LLM provider adapters.

Adapters register themselves under a name; the active provider is chosen by
`settings.LLM_PROVIDER` at resolve time. This is the only place provider
selection happens, so adding GPT/Claude/Gemini later means writing an adapter and
registering it -- nothing above this module changes.

No adapter is bundled here. Until one is registered and selected, `get_provider`
raises LLMConfigurationError rather than silently returning a fake, so a
misconfigured deployment fails loudly instead of producing bogus classifications.
"""

from __future__ import annotations

from typing import Callable

from app.services.llm.base import LLMConfigurationError, LLMProvider

# name -> zero-arg factory that builds a ready-to-use provider instance.
_FACTORIES: dict[str, Callable[[], LLMProvider]] = {}
_builtins_loaded = False


def _ensure_builtins_loaded() -> None:
    """Import the built-in adapter package once, so its adapters self-register.

    Done lazily (not at module import) so the deterministic pipeline never pulls
    in the provider adapters.
    """
    global _builtins_loaded
    if not _builtins_loaded:
        _builtins_loaded = True
        import app.services.llm.providers  # noqa: F401  (registers built-ins)


def register_provider(name: str, factory: Callable[[], LLMProvider]) -> None:
    """Register a provider adapter factory under a stable name.

    Called at import time by each adapter module (Step: LLM adapters). Idempotent
    re-registration is allowed so hot-reload in dev does not raise.
    """
    _FACTORIES[name] = factory


def available_providers() -> list[str]:
    _ensure_builtins_loaded()
    return sorted(_FACTORIES)


def get_provider(name: str) -> LLMProvider:
    """Build the provider registered under `name`.

    Raises LLMConfigurationError if nothing is registered under that name -- the
    expected state until the first adapter lands.
    """
    _ensure_builtins_loaded()
    factory = _FACTORIES.get(name)
    if factory is None:
        raise LLMConfigurationError(
            f"No LLM provider registered as {name!r}. "
            f"Registered: {available_providers() or 'none'}."
        )
    return factory()
