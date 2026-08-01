"""Anthropic Messages adapter.

Anthropic separates the system prompt from the conversation and requires
max_tokens, so this adapter lifts system messages into the top-level `system`
field and supplies a default max_tokens when the request omits one.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.llm.base import LLMRequest, LLMResponse, LLMRole, LLMUsage
from app.services.llm.providers._base import BaseHTTPLLMProvider
from app.services.llm.registry import register_provider

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_MAX_TOKENS = 1024


class AnthropicLLMProvider(BaseHTTPLLMProvider):
    name = "anthropic"

    @classmethod
    def from_settings(cls) -> "AnthropicLLMProvider":
        return cls(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.LLM_MODEL or _DEFAULT_MODEL,
            base_url=settings.ANTHROPIC_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            backoff=settings.PROVIDER_BACKOFF_SECONDS,
        )

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/messages"

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": settings.ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _build_payload(self, request: LLMRequest) -> dict:
        system_text = "\n\n".join(
            m.content for m in request.messages if m.role == LLMRole.SYSTEM
        )
        conversation = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role in (LLMRole.USER, LLMRole.ASSISTANT)
        ]
        payload: dict = {
            "model": self.model,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
            "messages": conversation,
            # No sampling params: current Claude models (Sonnet 5 / Opus 5 / 4.7+)
            # reject a non-default `temperature`/`top_p`/`top_k` with a 400, and the
            # classifier requests temperature=0. Determinism now comes from the task
            # shape, not sampling. Thinking is disabled: this is a fast, high-volume
            # Green/Amber/Red classifier returning a small JSON object -- adaptive
            # thinking (on by default on the 5-series) would add latency and cost and
            # compete with max_tokens for the response budget.
            "thinking": {"type": "disabled"},
        }
        if system_text:
            payload["system"] = system_text
        return payload

    def _parse(self, data: dict, request: LLMRequest) -> LLMResponse:
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider=self.name,
            usage=LLMUsage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            ),
            raw=None,
        )


register_provider("anthropic", AnthropicLLMProvider.from_settings)
