"""Shared HTTP base for embedding provider adapters (synchronous).

Same resilience and boundary rules as the LLM base: retries/backoff/timeout,
429/5xx and malformed handling, metadata-only logging, a single `_send` seam
with lazy httpx, and only provider-agnostic types (`list[float]`) crossing out.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass

from app.core.logger import logger
from app.services.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    EmbeddingProviderError,
)


class _TransportError(Exception):
    """Internal: a retryable transport failure."""


@dataclass(frozen=True)
class _HttpResult:
    status_code: int
    json: dict | None
    text: str
    retry_after: float | None = None


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class BaseHTTPEmbeddingProvider(EmbeddingProvider):
    name: str = "base"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff: float = 0.5,
        sender=None,
    ):
        if not api_key:
            raise EmbeddingConfigurationError(f"{self.name}: API key is not configured.")
        self.api_key = api_key
        self.model = model
        self.dimension = dimension
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._sender = sender

    # --- Public contract --------------------------------------------------

    def embed(self, text: str) -> list[float]:
        data = self._post_with_retries(self._endpoint(), self._headers(), self._build_payload(text))
        try:
            vector = self._parse(data)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError(
                f"{self.name}: response missing expected fields"
            ) from exc
        if len(vector) != self.dimension:
            raise EmbeddingProviderError(
                f"{self.name}: returned {len(vector)} dims, expected {self.dimension}"
            )
        return vector

    # --- Vendor hooks -----------------------------------------------------

    @abc.abstractmethod
    def _endpoint(self) -> str: ...

    @abc.abstractmethod
    def _headers(self) -> dict: ...

    @abc.abstractmethod
    def _build_payload(self, text: str) -> dict: ...

    @abc.abstractmethod
    def _parse(self, data: dict) -> list[float]: ...

    # --- Resilient request loop -------------------------------------------

    def _post_with_retries(self, url: str, headers: dict, payload: dict) -> dict:
        last: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            start = time.perf_counter()
            try:
                result = self._send(url, headers, payload)
            except _TransportError as exc:
                last = exc
                self._log_retry("transport_error", attempt, None, start)
                if attempt > self.max_retries:
                    break
                self._backoff(attempt, None)
                continue

            status = result.status_code
            if status == 429 or 500 <= status < 600:
                last = EmbeddingProviderError(f"{self.name}: HTTP {status}")
                self._log_retry("http_error", attempt, status, start)
                if attempt > self.max_retries:
                    break
                self._backoff(attempt, result.retry_after)
                continue
            if status >= 400:
                raise EmbeddingProviderError(f"{self.name}: HTTP {status} {result.text[:200]}")
            if result.json is None:
                last = EmbeddingProviderError(f"{self.name}: non-JSON response")
                self._log_retry("malformed_json", attempt, status, start)
                if attempt > self.max_retries:
                    break
                self._backoff(attempt, None)
                continue

            logger.info(
                "embedding provider request ok",
                extra={"provider": self.name, "model": self.model,
                       "status": status, "latency_ms": _ms(start)},
            )
            return result.json

        raise EmbeddingProviderError(
            f"{self.name}: request failed after {self.max_retries + 1} attempts: {last}"
        )

    def _send(self, url: str, headers: dict, payload: dict) -> _HttpResult:
        if self._sender is not None:
            return self._sender(url, headers, payload)
        import httpx

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise _TransportError(f"timeout after {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise _TransportError(str(exc)) from exc

        try:
            body = resp.json()
        except Exception:
            body = None
        return _HttpResult(
            resp.status_code, body, resp.text, _parse_retry_after(resp.headers.get("retry-after"))
        )

    def _backoff(self, attempt: int, retry_after: float | None) -> None:
        delay = retry_after if retry_after is not None else self.backoff * (2 ** (attempt - 1))
        time.sleep(delay)

    def _log_retry(self, reason: str, attempt: int, status: int | None, start: float) -> None:
        logger.warning(
            "embedding provider request ret/failed",
            extra={"provider": self.name, "model": self.model, "reason": reason,
                   "attempt": attempt, "status": status, "latency_ms": _ms(start)},
        )
