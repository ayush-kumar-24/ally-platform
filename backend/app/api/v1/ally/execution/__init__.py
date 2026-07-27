"""Ally AI Execution Layer (Phase 5, Milestone 5).

The first layer that talks to an LLM -- through the LLMProvider abstraction only.
Deterministic routing (AIRouter) -> provider-agnostic call (LLMProvider) with
retries/timeouts -> validation (ResponseParser) -> typed AIResponse. Fail-closed:
timeouts, failures and invalid responses yield an empty AIResponse, never fabricated
text. Offline-testable via MockLLMProvider (no SDK, no network).
"""

from app.api.v1.ally.execution.errors import (
    ExecutionError,
    InvalidResponseFieldError,
    InvalidResponseJSONError,
    MissingResponseFieldError,
    ResponseValidationError,
)
from app.api.v1.ally.execution.parser import ResponseParser
from app.api.v1.ally.execution.provider import LLMProvider, MockLLMProvider
from app.api.v1.ally.execution.router import AIRouter, RoutingPolicy
from app.api.v1.ally.execution.schemas import (
    AIRequest,
    AIResponse,
    ExecutionMetadata,
    ProviderHealth,
    ProviderMetadata,
    ProviderRequest,
    ProviderResponse,
    ResponseType,
    RoutingDecision,
    TokenUsage,
)
from app.api.v1.ally.execution.service import (
    AIExecutionService,
    build_execution_service,
)

__all__ = [
    "AIExecutionService",
    "build_execution_service",
    "AIRouter",
    "RoutingPolicy",
    "ResponseParser",
    "LLMProvider",
    "MockLLMProvider",
    "AIRequest",
    "AIResponse",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderHealth",
    "ProviderMetadata",
    "RoutingDecision",
    "ExecutionMetadata",
    "TokenUsage",
    "ResponseType",
    "ExecutionError",
    "ResponseValidationError",
    "InvalidResponseJSONError",
    "MissingResponseFieldError",
    "InvalidResponseFieldError",
]
