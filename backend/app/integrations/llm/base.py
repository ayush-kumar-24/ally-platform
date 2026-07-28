"""HTTP LLM provider: implements the FROZEN M5 `LLMProvider` interface once, over
httpx (no vendor SDK), and delegates every vendor-specific detail to a
`RequestAdapter`. Composition over inheritance -- one call path, N adapters.

The provider uses its OWN configured model (not `request.model`): under failover the
router emits a single model but each provider in the chain must call its own API
with its own model, so provider config wins.

Response contract: M5's ResponseParser expects a JSON body with a `content` field.
Real models return free text, so `_envelope` wraps the completion into that shape --
format adaptation only, no content is invented.

Health: every call outcome is recorded into a ProviderHealthState (latency, last
success/failure, consecutive failures) for the failover chain to read.
"""

from __future__ import annotations

import json
from time import perf_counter

import httpx

from app.api.v1.ally.execution.provider import LLMProvider
from app.api.v1.ally.execution.schemas import (
    ProviderHealth,
    ProviderMetadata,
    ProviderRequest,
    ProviderResponse,
)
from app.integrations.llm.adapters import DEFAULT_OPTIONS, GenerationOptions, RequestAdapter
from app.integrations.llm.errors import (
    LLMAuthError,
    LLMProviderCallError,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.integrations.llm.health import ProviderHealthState


def _envelope(text: str) -> str:
    """Wrap a model completion into the JSON body the M5 parser expects."""
    return json.dumps(
        {"content": text, "response_type": "answer", "confidence": None, "citations": []}
    )


class HttpLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        adapter: RequestAdapter,
        api_key: str,
        model: str | None = None,
        base_url: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
        options: GenerationOptions | None = None,
        health_state: ProviderHealthState | None = None,
    ):
        self._adapter = adapter
        self._api_key = api_key
        self._model = model or adapter.default_model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._options = options or DEFAULT_OPTIONS
        self._health = health_state or ProviderHealthState(
            provider=adapter.provider_name, model=self._model
        )

    @property
    def name(self) -> str:
        return self._adapter.provider_name

    # --- LLMProvider interface -------------------------------------------

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        start = perf_counter()
        try:
            response = self._client_or_default().post(
                self._adapter.endpoint(self._base_url, self._model, self._api_key),
                headers=self._adapter.headers(self._api_key),
                json=self._adapter.build_payload(request, self._model, self._options),
            )
            self._raise_for_status(response)
            text, usage, finish = self._adapter.parse(response.json())
        except httpx.TimeoutException as exc:
            self._health.record_failure()
            raise TimeoutError(f"{self.name} request timed out: {exc}") from exc
        except LLMProviderCallError:
            self._health.record_failure()  # includes rate-limit / auth / unavailable (subclasses)
            raise
        except httpx.HTTPError as exc:  # connect/read/transport errors
            self._health.record_failure()
            raise LLMUnavailableError(f"{self.name} transport error: {exc}") from exc
        except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            self._health.record_failure()
            raise LLMProviderCallError(f"{self.name} returned an unexpected body: {exc}") from exc

        self._health.record_success((perf_counter() - start) * 1000)
        return ProviderResponse(
            content=_envelope(text), finish_reason=finish or "stop",
            token_usage=usage, model=self._model, provider=self.name,
        )

    def health(self) -> ProviderHealth:
        # Frozen M5 DTO derived from the live state (config gates it too: no key -> down).
        healthy = bool(self._api_key) and self._health.healthy
        detail = (
            f"{self.name}: no api key" if not self._api_key
            else f"{self.name} healthy" if healthy
            else f"{self.name} unhealthy ({self._health.failures} failures)"
        )
        return ProviderHealth(healthy=healthy, detail=detail)

    def health_state(self) -> ProviderHealthState:
        """The live, rich health state (latency, timestamps, failure count)."""
        return self._health

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name=self.name, models=(self._model,), supports_json=True)

    # --- Shared HTTP helpers ---------------------------------------------

    def _client_or_default(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _raise_for_status(self, response: httpx.Response) -> None:
        code = response.status_code
        if code == 429:
            raise LLMRateLimitError(f"{self.name} rate limited (429)")
        if code in (401, 403):
            raise LLMAuthError(f"{self.name} authentication failed ({code})")
        if code >= 500:
            raise LLMUnavailableError(f"{self.name} unavailable ({code})")
        if code >= 400:
            raise LLMProviderCallError(f"{self.name} error {code}: {response.text[:200]}")


# Backward-compatible alias (the earlier abstract base name).
BaseHttpLLMProvider = HttpLLMProvider
