"""Provider-agnostic LLM service.

Public surface: the `LLMProvider` contract, its transport types, and the
registry used to select a concrete adapter by configuration.
"""

from app.services.llm.base import (
    LLMConfigurationError,
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    LLMRole,
    LLMUsage,
)
from app.services.llm.registry import (
    available_providers,
    get_provider,
    register_provider,
)

__all__ = [
    "LLMConfigurationError",
    "LLMError",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMResponse",
    "LLMRole",
    "LLMUsage",
    "available_providers",
    "get_provider",
    "register_provider",
]
