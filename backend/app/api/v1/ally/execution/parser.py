"""Response Parser -- validates a raw provider response into an AIResponse.

Validation ONLY. It never generates or rewrites text: it parses the JSON body,
checks the required and optional fields, and packages the already-present values.
On any problem it raises a typed ResponseValidationError -- it never substitutes a
default or invents content. The Execution Service attaches ExecutionMetadata
afterwards (the parser does not know about attempts/timeouts).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from app.api.v1.ally.execution.errors import (
    InvalidResponseFieldError,
    InvalidResponseJSONError,
    MissingResponseFieldError,
)
from app.api.v1.ally.execution.schemas import (
    AIResponse,
    ProviderResponse,
    ResponseType,
    TokenUsage,
)

_VALID_TYPES = {t.value for t in ResponseType}


class ResponseParser:
    def parse(self, response: ProviderResponse) -> AIResponse:
        data = self._load_json(response.content)

        content = data.get("content")
        if not isinstance(content, str) or not content.strip():
            raise MissingResponseFieldError("response is missing a non-empty 'content'")

        response_type = data.get("response_type", ResponseType.ANSWER.value)
        if response_type not in _VALID_TYPES:
            raise InvalidResponseFieldError(
                f"invalid response_type {response_type!r}; expected one of {sorted(_VALID_TYPES)}"
            )

        confidence = self._parse_confidence(data.get("confidence"))
        citations = self._parse_citations(data.get("citations"))
        token_usage = self._validate_usage(response.token_usage)

        return AIResponse(
            ok=True,
            content=content,
            response_type=response_type,
            confidence=confidence,
            citations=citations,
            token_usage=token_usage,
            metadata=None,          # attached by the Execution Service
        )

    def _load_json(self, body: str) -> dict:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidResponseJSONError(f"response body is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise InvalidResponseJSONError("response JSON must be an object")
        return data

    def _parse_confidence(self, value) -> Decimal | None:
        if value is None:
            return None
        try:
            conf = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise InvalidResponseFieldError(f"confidence is not numeric: {value!r}") from exc
        if not (Decimal("0") <= conf <= Decimal("1")):
            raise InvalidResponseFieldError(f"confidence {conf} out of range [0, 1]")
        return conf

    def _parse_citations(self, value) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
            raise InvalidResponseFieldError("citations must be a list of strings")
        return tuple(value)

    def _validate_usage(self, usage: TokenUsage) -> TokenUsage:
        if usage.prompt_tokens < 0 or usage.completion_tokens < 0 or usage.total_tokens < 0:
            raise InvalidResponseFieldError("token usage counts must be non-negative")
        return usage
