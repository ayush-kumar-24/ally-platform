"""OpenAI Chat Completions adapter."""

from __future__ import annotations

from app.core.config import settings
from app.services.llm.base import LLMRequest, LLMResponse, LLMRole, LLMUsage
from app.services.llm.providers._base import BaseHTTPLLMProvider
from app.services.llm.registry import register_provider

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAILLMProvider(BaseHTTPLLMProvider):
    name = "openai"

    @classmethod
    def from_settings(cls) -> "OpenAILLMProvider":
        return cls(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL or _DEFAULT_MODEL,
            base_url=settings.OPENAI_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            backoff=settings.PROVIDER_BACKOFF_SECONDS,
        )

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _build_payload(self, request: LLMRequest) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        return payload

    def _parse(self, data: dict, request: LLMRequest) -> LLMResponse:
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=data.get("model", self.model),
            provider=self.name,
            usage=LLMUsage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            ),
            raw=None,
        )


register_provider("openai", OpenAILLMProvider.from_settings)
