"""Shared HTTP base for LLM provider adapters.

Owns the cross-vendor concerns -- retries, exponential backoff, timeout,
rate-limit (429) and 5xx handling, malformed-response handling, and structured
logging -- so each vendor adapter only maps requests/responses.

Boundary rules:
  * The single I/O seam is `_send`; it lazily imports httpx so importing an
    adapter never requires httpx, and tests inject a fake sender.
  * Only provider-agnostic types cross the boundary: `generate` returns an
    `LLMResponse`. No vendor object or vendor JSON structure is exposed
    (`LLMResponse.raw` is left None).
  * Logs carry metadata only (provider, model, status, attempt, latency) -- never
    API keys, prompts, or response bodies.
"""

from __future__ import annotations

import abc
import asyncio
import time
from dataclasses import dataclass

from app.core.logger import logger
from app.services.llm.base import (
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)


class _TransportError(Exception):
    """Internal: a retryable transport failure (timeout, connection reset)."""


@dataclass(frozen=True)
class _HttpResult:
    status_code: int
    json: dict | None
    text: str
    retry_after: float | None = None


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class BaseHTTPLLMProvider(LLMProvider):
    """Template for HTTP-based LLM adapters. Subclasses implement the vendor
    mapping methods; this class runs the resilient request loop."""

    name: str = "base"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff: float = 0.5,
        sender=None,
    ):
        if not api_key:
            raise LLMConfigurationError(f"{self.name}: API key is not configured.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._sender = sender  # test seam; production uses httpx in _send

    # --- Public contract --------------------------------------------------

    def with_model(self, model_id: str) -> "BaseHTTPLLMProvider":
        """Pin this provider instance to a specific model (task->model routing).
        Safe because the registry builds a fresh instance per resolve."""
        self.model = model_id
        return self

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        data = await self._post_with_retries(self._endpoint(), self._headers(), payload)
        try:
            return self._parse(data, request)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError(
                f"{self.name}: response missing expected fields"
            ) from exc

    # --- Vendor hooks (implemented by subclasses) -------------------------

    @abc.abstractmethod
    def _endpoint(self) -> str: ...

    @abc.abstractmethod
    def _headers(self) -> dict: ...

    @abc.abstractmethod
    def _build_payload(self, request: LLMRequest) -> dict: ...

    @abc.abstractmethod
    def _parse(self, data: dict, request: LLMRequest) -> LLMResponse: ...

    # --- Resilient request loop -------------------------------------------

    async def _post_with_retries(self, url: str, headers: dict, payload: dict) -> dict:
        last: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            start = time.perf_counter()
            try:
                result = await self._send(url, headers, payload)
            except _TransportError as exc:
                last = exc
                self._log_retry("transport_error", attempt, None, start)
                if attempt > self.max_retries:
                    break
                await self._backoff(attempt, None)
                continue

            status = result.status_code
            if status == 429 or 500 <= status < 600:
                last = LLMProviderError(f"{self.name}: HTTP {status}")
                self._log_retry("http_error", attempt, status, start)
                if attempt > self.max_retries:
                    break
                await self._backoff(attempt, result.retry_after)
                continue
            if status >= 400:
                # 4xx (auth, bad request) is not retryable.
                raise LLMProviderError(f"{self.name}: HTTP {status} {result.text[:200]}")
            if result.json is None:
                last = LLMProviderError(f"{self.name}: non-JSON response")
                self._log_retry("malformed_json", attempt, status, start)
                if attempt > self.max_retries:
                    break
                await self._backoff(attempt, None)
                continue

            logger.info(
                "llm provider request ok",
                extra={"provider": self.name, "model": self.model,
                       "status": status, "latency_ms": _ms(start)},
            )
            return result.json

        raise LLMProviderError(
            f"{self.name}: request failed after {self.max_retries + 1} attempts: {last}"
        )

    async def _send(self, url: str, headers: dict, payload: dict) -> _HttpResult:
        if self._sender is not None:
            return await self._sender(url, headers, payload)
        import httpx  # lazy: importing the adapter never requires httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise _TransportError(f"timeout after {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise _TransportError(str(exc)) from exc

        try:
            body = resp.json()
        except Exception:
            body = None
        return _HttpResult(
            resp.status_code, body, resp.text, parse_retry_after(resp.headers.get("retry-after"))
        )

    async def _backoff(self, attempt: int, retry_after: float | None) -> None:
        delay = retry_after if retry_after is not None else self.backoff * (2 ** (attempt - 1))
        await asyncio.sleep(delay)

    def _log_retry(self, reason: str, attempt: int, status: int | None, start: float) -> None:
        logger.warning(
            "llm provider request ret/failed",
            extra={"provider": self.name, "model": self.model, "reason": reason,
                   "attempt": attempt, "status": status, "latency_ms": _ms(start)},
        )
