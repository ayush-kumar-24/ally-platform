"""Provider request/response adapters.

Each vendor's wire format (endpoint, headers, payload shape, response parsing) is
isolated in a RequestAdapter, so the HTTP provider is vendor-agnostic and new
capabilities (reasoning effort, tools, response format, streaming) are added in one
place per vendor via GenerationOptions -- not scattered across providers.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from app.api.v1.ally.execution.schemas import ProviderRequest, TokenUsage


@dataclass(frozen=True)
class GenerationOptions:
    """Optional generation controls, applied by adapters when set. Defaulted to
    no-ops so today's payloads are unchanged; future callers populate these."""

    reasoning_effort: str | None = None      # e.g. "low" | "medium" | "high"
    response_format: str | None = None       # e.g. "json"
    tools: tuple[Any, ...] | None = None
    stream: bool = False


DEFAULT_OPTIONS = GenerationOptions()


class RequestAdapter(abc.ABC):
    provider_name: str = "base"
    default_model: str = ""

    @abc.abstractmethod
    def endpoint(self, base_url: str, model: str, api_key: str) -> str: ...

    @abc.abstractmethod
    def headers(self, api_key: str) -> dict: ...

    @abc.abstractmethod
    def build_payload(self, request: ProviderRequest, model: str, options: GenerationOptions) -> dict: ...

    @abc.abstractmethod
    def parse(self, data: dict) -> tuple[str, TokenUsage, str | None]: ...


class OpenAIAdapter(RequestAdapter):
    provider_name = "openai"
    default_model = "gpt-4o-mini"

    def endpoint(self, base_url, model, api_key):
        return f"{base_url}/chat/completions"

    def headers(self, api_key):
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def build_payload(self, request, model, options):
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": float(request.temperature),
            # Current models (gpt-5.x and later) reject `max_tokens` outright --
            # "Unsupported parameter... Use 'max_completion_tokens' instead"
            # (HTTP 400). That 400 was being swallowed by FailoverLLMProvider's
            # blanket except-and-continue with no logging, so every real OpenAI
            # call failed silently and every chat reply came from the mock
            # fallback with ok=True and no visible error anywhere. Confirmed
            # empirically against the real API with the configured OPENAI_MODEL.
            "max_completion_tokens": request.max_tokens,
        }
        if options.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        if options.tools:
            payload["tools"] = list(options.tools)
        if options.reasoning_effort:
            payload["reasoning_effort"] = options.reasoning_effort
        if options.stream:
            payload["stream"] = True
        return payload

    def parse(self, data):
        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )
        return text, token_usage, choice.get("finish_reason")


class ClaudeAdapter(RequestAdapter):
    provider_name = "anthropic"
    # claude-3-5-sonnet-latest no longer resolves (Anthropic 404s it) -- see
    # the same stale-default fix in app/integrations/llm/settings.py. This
    # class attribute is a fallback for direct construction without an
    # explicit model; nothing in the live app relies on it today, but keeping
    # a second stale copy around is how this drifted in the first place.
    default_model = "claude-sonnet-5"
    _API_VERSION = "2023-06-01"

    def endpoint(self, base_url, model, api_key):
        return f"{base_url}/v1/messages"

    def headers(self, api_key):
        return {"x-api-key": api_key, "anthropic-version": self._API_VERSION, "content-type": "application/json"}

    def build_payload(self, request, model, options):
        payload: dict = {
            "model": model,
            "max_tokens": request.max_tokens,
            "system": request.system,          # system is a top-level field for Claude
            "messages": [{"role": "user", "content": request.user}],
            # `temperature` deliberately omitted: the Claude 5 family (sonnet-5,
            # opus-5 -- confirmed empirically; haiku-4-5 still accepts it)
            # rejects it outright with HTTP 400 "`temperature` is deprecated
            # for this model." Sending it unconditionally broke every real
            # Anthropic call the moment reasoning-tier routing started
            # actually reaching this provider (previously it was only ever a
            # silent, unlogged failover link -- see FailoverLLMProvider).
        }
        if options.tools:
            payload["tools"] = list(options.tools)
        return payload

    def parse(self, data):
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type", "text") == "text")
        usage = data.get("usage", {})
        token_usage = TokenUsage.of(int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))
        return text, token_usage, data.get("stop_reason")


class GeminiAdapter(RequestAdapter):
    provider_name = "gemini"
    default_model = "gemini-1.5-flash"

    def endpoint(self, base_url, model, api_key):
        return f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"

    def headers(self, api_key):
        return {"Content-Type": "application/json"}

    def build_payload(self, request, model, options):
        gen: dict = {"temperature": float(request.temperature), "maxOutputTokens": request.max_tokens}
        if options.response_format == "json":
            gen["responseMimeType"] = "application/json"
        payload: dict = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [{"role": "user", "parts": [{"text": request.user}]}],
            "generationConfig": gen,
        }
        if options.tools:
            payload["tools"] = list(options.tools)
        return payload

    def parse(self, data):
        candidate = data["candidates"][0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        token_usage = TokenUsage.of(int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)))
        return text, token_usage, candidate.get("finishReason")
