"""Config-driven registry of embedding adapters.

Same pattern as the LLM registry: adapters register a factory under a name; the
active one is chosen by `settings.EMBEDDING_PROVIDER`. Until an adapter is
registered and selected, `get_provider` raises EmbeddingConfigurationError rather
than returning a fake -- a misconfigured deployment fails loudly instead of
producing meaningless vectors.
"""

from __future__ import annotations

from typing import Callable

from app.services.embeddings.base import EmbeddingConfigurationError, EmbeddingProvider

_FACTORIES: dict[str, Callable[[], EmbeddingProvider]] = {}
_builtins_loaded = False


def _ensure_builtins_loaded() -> None:
    """Import the built-in adapters once so they self-register. Lazy, so a
    retrieval-disabled deployment never imports them."""
    global _builtins_loaded
    if not _builtins_loaded:
        _builtins_loaded = True
        import app.services.embeddings.providers  # noqa: F401  (registers built-ins)


def register_provider(name: str, factory: Callable[[], EmbeddingProvider]) -> None:
    _FACTORIES[name] = factory


def available_providers() -> list[str]:
    _ensure_builtins_loaded()
    return sorted(_FACTORIES)


def get_provider(name: str) -> EmbeddingProvider:
    _ensure_builtins_loaded()
    factory = _FACTORIES.get(name)
    if factory is None:
        raise EmbeddingConfigurationError(
            f"No embedding provider registered as {name!r}. "
            f"Registered: {available_providers() or 'none'}."
        )
    return factory()
