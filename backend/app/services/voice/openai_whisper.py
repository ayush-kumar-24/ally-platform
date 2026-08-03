"""OpenAI Whisper transcription adapter.

Multipart, not JSON -- the one real difference from the embeddings/LLM HTTP
bases in this codebase, which are JSON-only. Kept as its own small client rather
than shoehorned into BaseHTTPEmbeddingProvider (whose `_build_payload`/`_send`
are JSON-shaped throughout). Same resilience shape as those bases: bounded
retries on 429/5xx and transport errors, fails loud otherwise.
"""

from __future__ import annotations

import time

from app.core.config import settings
from app.core.logger import logger
from app.services.voice.base import TranscriptionError, TranscriptionProvider

_DEFAULT_MODEL = "whisper-1"


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


class OpenAIWhisperProvider(TranscriptionProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff: float = 0.5,
        sender=None,
    ):
        if not api_key:
            raise TranscriptionError("openai: API key is not configured.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._sender = sender  # test seam: (url, headers, files, data) -> _HttpResult

    @classmethod
    def from_settings(cls) -> "OpenAIWhisperProvider":
        return cls(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            backoff=settings.PROVIDER_BACKOFF_SECONDS,
        )

    def transcribe(self, audio: bytes, *, filename: str, content_type: str) -> str:
        url = f"{self.base_url}/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"model": self.model}
        files = {"file": (filename, audio, content_type or "application/octet-stream")}

        last: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            start = time.perf_counter()
            try:
                result = self._send(url, headers, files, data)
            except _TransportError as exc:
                last = exc
                self._log_retry("transport_error", attempt, None, start)
                if attempt > self.max_retries:
                    break
                time.sleep(self.backoff * (2 ** (attempt - 1)))
                continue

            if result.status_code == 429 or 500 <= result.status_code < 600:
                last = TranscriptionError(f"openai: HTTP {result.status_code}")
                self._log_retry("http_error", attempt, result.status_code, start)
                if attempt > self.max_retries:
                    break
                time.sleep(self.backoff * (2 ** (attempt - 1)))
                continue
            if result.status_code >= 400:
                raise TranscriptionError(f"openai: HTTP {result.status_code} {result.text[:200]}")
            if result.json is None or "text" not in result.json:
                raise TranscriptionError("openai: response missing 'text'")

            logger.info(
                "voice transcription ok",
                extra={"provider": self.name, "model": self.model,
                       "status": result.status_code, "latency_ms": _ms(start)},
            )
            return result.json["text"]

        raise TranscriptionError(
            f"openai: request failed after {self.max_retries + 1} attempts: {last}"
        )

    def _send(self, url, headers, files, data):
        if self._sender is not None:
            return self._sender(url, headers, files, data)
        import httpx

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, files=files, data=data)
        except httpx.TimeoutException as exc:
            raise _TransportError(f"timeout after {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise _TransportError(str(exc)) from exc

        try:
            body = resp.json()
        except Exception:
            body = None
        return _HttpResult(resp.status_code, body, resp.text)

    def _log_retry(self, reason: str, attempt: int, status: int | None, start: float) -> None:
        logger.warning(
            "voice transcription retry/failed",
            extra={"provider": self.name, "model": self.model, "reason": reason,
                   "attempt": attempt, "status": status, "latency_ms": _ms(start)},
        )


class _TransportError(Exception):
    """Internal: a retryable transport failure."""


class _HttpResult:
    def __init__(self, status_code: int, json_body: dict | None, text: str):
        self.status_code = status_code
        self.json = json_body
        self.text = text
