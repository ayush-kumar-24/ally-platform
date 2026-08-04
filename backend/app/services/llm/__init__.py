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
from app.services.llm.router import LLMTask, TaskModel, resolve_task_model
from app.services.llm.tasks import provider_for_task
from app.services.llm.telemetry import estimate_cost

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
    "LLMTask",
    "TaskModel",
    "resolve_task_model",
    "provider_for_task",
    "estimate_cost",
]
