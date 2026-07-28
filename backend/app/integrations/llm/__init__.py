"""Real LLM provider adapters for the Ally AI Execution layer.

Implement the FROZEN M5 `LLMProvider` interface over httpx (no vendor SDKs), so the
AIExecutionService, AgentOrchestrator, PromptManager and Retrieval are all
unchanged -- only the provider implementations are new.

Structure:
  - adapters.py  : per-vendor wire format (RequestAdapter + GenerationOptions)
  - base.py      : one HttpLLMProvider call path, composed with an adapter
  - *_provider.py: thin adapter wiring (OpenAI / Claude / Gemini)
  - health.py    : rich, live provider health state
  - routing.py   : LLMRoutingConfig (routing as config) + FailoverLLMProvider
  - settings.py  : environment snapshot + simple provider/router factories
"""

from app.integrations.llm.adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    GenerationOptions,
    OpenAIAdapter,
    RequestAdapter,
)
from app.integrations.llm.anthropic_provider import ClaudeProvider
from app.integrations.llm.base import BaseHttpLLMProvider, HttpLLMProvider
from app.integrations.llm.errors import (
    LLMAuthError,
    LLMProviderCallError,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.integrations.llm.gemini_provider import GeminiProvider
from app.integrations.llm.health import HealthRegistry, ProviderHealthState
from app.integrations.llm.openai_provider import OpenAIProvider
from app.integrations.llm.routing import (
    FailoverLLMProvider,
    LLMRoutingConfig,
    build_failover_execution,
    build_provider_registry,
)
from app.integrations.llm.settings import (
    LLMSettings,
    build_providers,
    build_routing_policy,
)

__all__ = [
    # providers
    "OpenAIProvider",
    "ClaudeProvider",
    "GeminiProvider",
    "HttpLLMProvider",
    "BaseHttpLLMProvider",
    "FailoverLLMProvider",
    # adapters
    "RequestAdapter",
    "OpenAIAdapter",
    "ClaudeAdapter",
    "GeminiAdapter",
    "GenerationOptions",
    # health
    "ProviderHealthState",
    "HealthRegistry",
    # config / factories
    "LLMRoutingConfig",
    "LLMSettings",
    "build_failover_execution",
    "build_provider_registry",
    "build_providers",
    "build_routing_policy",
    # errors
    "LLMProviderCallError",
    "LLMRateLimitError",
    "LLMAuthError",
    "LLMUnavailableError",
]
