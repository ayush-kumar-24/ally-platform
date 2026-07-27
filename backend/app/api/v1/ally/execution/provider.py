"""LLM provider abstraction + a deterministic offline mock.

`LLMProvider` is the seam nothing outside crosses: the router names a provider, the
service calls `generate` -- neither knows the vendor. Real adapters (OpenAI,
Anthropic, Gemini, Azure, Groq, OpenRouter) are added later as implementations of
this ABC; each wraps its own client behind `generate/health/metadata`.

`MockLLMProvider` is fully offline -- no SDK, no network, no API key. It is
deterministic given its configuration and the request, and it can simulate
timeouts, failures (with retry windows) and malformed bodies for testing.
"""

from __future__ import annotations

import abc
import json

from app.api.v1.ally.execution.schemas import (
    ProviderHealth,
    ProviderMetadata,
    ProviderRequest,
    ProviderResponse,
    TokenUsage,
)


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Produce a completion. May raise TimeoutError or any Exception; the
        Execution Service handles those as fail-closed empty responses."""
        raise NotImplementedError

    @abc.abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    @abc.abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError


def _count_tokens(text: str) -> int:
    # Deterministic, offline token proxy (whitespace tokens). Not a real tokenizer.
    return len(text.split())


class MockLLMProvider(LLMProvider):
    """Deterministic, offline provider for testing.

    behaviour flags (applied in call order):
      * timeout_times : raise TimeoutError for the first N calls
      * fail_times    : then raise RuntimeError for the next N calls
      * raises        : always raise this (after the windows above)
      * content       : the exact body to return; default is a valid answer JSON
    """

    def __init__(
        self,
        *,
        name: str = "mock",
        models: tuple[str, ...] = ("mock-standard", "mock-careful"),
        content: str | None = None,
        raises: Exception | None = None,
        fail_times: int = 0,
        timeout_times: int = 0,
        healthy: bool = True,
    ):
        self.name = name
        self.models = models
        self._content = content
        self._raises = raises
        self._fail_times = fail_times
        self._timeout_times = timeout_times
        self._healthy = healthy
        self._calls = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self._calls += 1
        if self._calls <= self._timeout_times:
            raise TimeoutError("mock provider timeout")
        if self._calls <= self._timeout_times + self._fail_times:
            raise RuntimeError("mock provider failure")
        if self._raises is not None:
            raise self._raises

        body = self._content if self._content is not None else self._default_body(request)
        usage = TokenUsage.of(
            prompt=_count_tokens(request.system) + _count_tokens(request.user),
            completion=_count_tokens(body),
        )
        return ProviderResponse(
            content=body, finish_reason="stop", token_usage=usage,
            model=request.model, provider=self.name,
        )

    def _default_body(self, request: ProviderRequest) -> str:
        return json.dumps(
            {
                "content": f"Grounded answer from {request.model}.",
                "response_type": "answer",
                "confidence": 0.8,
                "citations": [],
            }
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(healthy=self._healthy, detail="mock")

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name=self.name, models=self.models, supports_json=True)
