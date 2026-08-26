"""Execution Service -- orchestrates Router -> Provider -> Parser.

Responsibilities: route, call the selected provider with retries, handle timeouts
and failures, and validate the result. Fail-closed at every edge: a timeout, a
provider failure, an unknown provider, or an invalid response all yield an EMPTY
AIResponse (ok=False) -- never fabricated fallback text.

Boundaries (enforced by imports): it imports the execution package and M2's
RenderedPrompt DTO only. No LLM SDK, no HTTP, no retrieval, no graph, no memory --
and Memory does not exist yet.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from app.api.v1.ally.execution.errors import ResponseValidationError
from app.api.v1.ally.execution.parser import ResponseParser
from app.api.v1.ally.execution.provider import LLMProvider
from app.api.v1.ally.execution.router import AIRouter
from app.api.v1.ally.execution.schemas import (
    AIRequest,
    AIResponse,
    ExecutionMetadata,
    ProviderRequest,
    RoutingDecision,
    TokenUsage,
)
from app.core.logger import logger


class AIExecutionService:
    def __init__(
        self,
        providers: Mapping[str, LLMProvider],
        *,
        router: AIRouter | None = None,
        parser: ResponseParser | None = None,
        max_retries: int = 2,
    ):
        self.providers = dict(providers)
        self.router = router or AIRouter()
        self.parser = parser or ResponseParser()
        self.max_retries = max_retries

    def execute(self, request: AIRequest) -> AIResponse:
        decision = self.router.route(request)

        provider = self.providers.get(decision.provider)
        if provider is None:
            return self._empty(decision, attempts=0, error=f"unknown provider {decision.provider!r}")

        provider_request = ProviderRequest(
            system=request.prompt.system_prompt,
            user=request.prompt.user_prompt,
            model=decision.model,
            temperature=decision.temperature,
            max_tokens=decision.max_tokens,
            media=request.media,
        )

        attempts = 0
        last_error: str | None = None
        timed_out = False
        while attempts <= self.max_retries:
            attempts += 1
            try:
                provider_response = provider.generate(provider_request)
            except TimeoutError as exc:
                timed_out = True
                last_error = f"timeout: {exc}"
                continue                      # retriable
            except Exception as exc:          # provider failure -> retriable
                last_error = f"provider_error: {exc}"
                continue

            # Got a response body. Validation errors are NOT retried (the call
            # succeeded; the body is just unusable) -> fail closed immediately.
            try:
                parsed = self.parser.parse(provider_response)
            except ResponseValidationError as exc:
                logger.warning(
                    "ai response failed validation; returning empty",
                    extra={"stage": "ai_execution", "error": str(exc)},
                )
                return self._empty(
                    decision, attempts=attempts, error=f"validation: {exc}",
                    token_usage=provider_response.token_usage,
                )

            metadata = ExecutionMetadata(
                provider=decision.provider, model=decision.model,
                temperature=decision.temperature, max_tokens=decision.max_tokens,
                attempts=attempts, succeeded=True, timed_out=False, error=None,
            )
            return replace(parsed, metadata=metadata)

        # Retries exhausted.
        logger.warning(
            "ai execution failed after retries; returning empty",
            extra={"stage": "ai_execution", "attempts": attempts, "error": last_error},
        )
        return self._empty(decision, attempts=attempts, error=last_error, timed_out=timed_out)

    def _empty(
        self,
        decision: RoutingDecision,
        *,
        attempts: int,
        error: str | None,
        timed_out: bool = False,
        token_usage: TokenUsage | None = None,
    ) -> AIResponse:
        metadata = ExecutionMetadata(
            provider=decision.provider, model=decision.model,
            temperature=decision.temperature, max_tokens=decision.max_tokens,
            attempts=attempts, succeeded=False, timed_out=timed_out, error=error,
        )
        return AIResponse(
            ok=False, content="", response_type="none", confidence=None,
            citations=(), token_usage=token_usage or TokenUsage(), metadata=metadata,
            error=error,
        )


def build_execution_service(
    providers: Mapping[str, LLMProvider],
    *,
    router: AIRouter | None = None,
    parser: ResponseParser | None = None,
    max_retries: int = 2,
) -> AIExecutionService:
    return AIExecutionService(providers, router=router, parser=parser, max_retries=max_retries)
