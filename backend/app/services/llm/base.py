"""Provider-agnostic LLM interface.

The reasoning layer must not depend on any single vendor. Everything above this
module talks to `LLMProvider`; concrete adapters for OpenAI / Anthropic / Gemini
/ etc. are registered separately (see registry.py) and selected by configuration
at runtime. No provider is imported or referenced here.

This module defines the contract and the transport types only -- it contains no
network code and no engine logic.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum


class LLMRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """A single completion request, expressed in provider-neutral terms.

    `response_format` is an optional hint (e.g. {"type": "json_object"}); adapters
    map it to whatever their vendor calls the equivalent, or ignore it. Keeping it
    a plain dict avoids leaking any vendor's schema into the interface.
    """

    messages: tuple[LLMMessage, ...]
    temperature: float = 0.0
    max_tokens: int | None = None
    response_format: dict | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    raw: dict | None = None


class LLMError(Exception):
    """Base class for provider-layer failures."""


class LLMConfigurationError(LLMError):
    """No provider is configured, or a required setting/credential is missing."""


class LLMProviderError(LLMError):
    """The provider was reached but the call failed (rate limit, upstream error,
    malformed response). Adapters wrap vendor exceptions in this so callers never
    catch vendor-specific types."""


class LLMProvider(abc.ABC):
    """The single contract every vendor adapter implements.

    Adapters are constructed with their own credentials/config and expose exactly
    one capability the reasoning layer needs: turn a request into a response.
    Kept async because every real provider call is I/O-bound network work.
    """

    #: Stable identifier used in configuration and logging, e.g. "anthropic".
    name: str

    @abc.abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Run one completion. Must raise LLMProviderError on any upstream
        failure and LLMConfigurationError on missing configuration."""
        raise NotImplementedError
