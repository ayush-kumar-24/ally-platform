"""Google Gemini generateContent adapter.

Gemini uses role "model" for the assistant, lifts the system prompt into
`systemInstruction`, and nests generation options under `generationConfig`.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.llm.base import LLMRequest, LLMResponse, LLMRole, LLMUsage
from app.services.llm.providers._base import BaseHTTPLLMProvider
from app.services.llm.registry import register_provider

_DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiLLMProvider(BaseHTTPLLMProvider):
    name = "gemini"

    @classmethod
    def from_settings(cls) -> "GeminiLLMProvider":
        return cls(
            api_key=settings.GEMINI_API_KEY,
            model=settings.LLM_MODEL or _DEFAULT_MODEL,
            base_url=settings.GEMINI_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            backoff=settings.PROVIDER_BACKOFF_SECONDS,
        )

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1beta/models/{self.model}:generateContent"

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def _build_payload(self, request: LLMRequest) -> dict:
        system_text = "\n\n".join(
            m.content for m in request.messages if m.role == LLMRole.SYSTEM
        )
        contents = [
            {
                "role": "user" if m.role == LLMRole.USER else "model",
                "parts": [{"text": m.content}],
            }
            for m in request.messages
            if m.role in (LLMRole.USER, LLMRole.ASSISTANT)
        ]
        generation_config: dict = {"temperature": request.temperature}
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.response_format and request.response_format.get("type") == "json_object":
            generation_config["responseMimeType"] = "application/json"

        payload: dict = {"contents": contents, "generationConfig": generation_config}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        return payload

    def _parse(self, data: dict, request: LLMRequest) -> LLMResponse:
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            usage=LLMUsage(
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
            ),
            raw=None,
        )


register_provider("gemini", GeminiLLMProvider.from_settings)
