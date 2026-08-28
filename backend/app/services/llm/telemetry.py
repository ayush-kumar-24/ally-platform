"""Per-call LLM telemetry: wrap any provider so every call logs model, tokens,
latency and estimated cost to `llm_call_log`.

Writing the log must NEVER break the call it describes: on a logging error we
swallow and continue. Pricing is reference data (a small per-model map), not the
routing decision -- the task->model decision lives in the DB (see router.py).
"""

from __future__ import annotations

import time
from decimal import Decimal

from app.core.logger import logger
from app.models.llm import LLMCallLog
from app.services.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

# USD per 1M tokens (input, output). Reference data -- edit when pricing changes.
# Sonnet 5 list price is $3/$15; intro $2/$10 through 2026-08-31. We record the
# LIST price so cost estimates don't silently jump when the intro window ends.
_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-5": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-haiku-4-5-20251001": (Decimal("1.00"), Decimal("5.00")),
}
_MILLION = Decimal("1000000")


def estimate_cost(model_id: str, input_tokens: int | None, output_tokens: int | None) -> Decimal | None:
    price = _PRICING.get(model_id)
    if price is None or input_tokens is None or output_tokens is None:
        return None
    in_rate, out_rate = price
    return (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / _MILLION


class LoggingLLMProvider(LLMProvider):
    """Decorator that records one llm_call_log row per generate() call.

    The log is written in its OWN short-lived session (thread-safe, and correct
    for observability: it persists even if the caller's transaction rolls back,
    and never entangles it). A logging failure is logged and swallowed, never
    raised -- telemetry must never break the call it describes. `session_factory`
    is injectable for tests; production uses SessionLocal.
    """

    def __init__(
        self,
        inner: LLMProvider,
        *,
        task: str,
        provider: str,
        model_id: str,
        founder_id: int | None = None,
        founder_uuid: str | None = None,
        session_id: int | None = None,
        session_factory=None,
    ):
        self._inner = inner
        self._task = task
        self._provider = provider
        self._model_id = model_id
        self._founder_id = founder_id
        self._founder_uuid = founder_uuid
        self._session_id = session_id
        self._session_factory = session_factory

    @property
    def name(self) -> str:  # pragma: no cover - passthrough
        return getattr(self._inner, "name", self._provider)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        try:
            response = await self._inner.generate(request)
        except LLMProviderError as exc:
            self._log(status="error", latency_ms=self._ms(start), error=str(exc)[:500])
            raise
        except Exception as exc:  # unexpected -- still record before re-raising
            self._log(status="error", latency_ms=self._ms(start), error=repr(exc)[:500])
            raise
        self._log(
            status="ok",
            latency_ms=self._ms(start),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return response

    @staticmethod
    def _ms(start: float) -> int:
        return int(round((time.perf_counter() - start) * 1000))

    def _log(self, *, status, latency_ms, input_tokens=None, output_tokens=None, error=None):
        row = LLMCallLog(
            task=self._task,
            provider=self._provider,
            model_id=self._model_id,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=(
                estimate_cost(self._model_id, input_tokens, output_tokens)
                if status == "ok" else None
            ),
            founder_id=self._founder_id,
            session_id=self._session_id,
            error=error,
        )
        factory = self._session_factory
        if factory is None:
            from app.db.session import SessionLocal  # lazy: own short-lived session
            factory = SessionLocal
        try:
            session = factory()
            try:
                if self._founder_uuid:
                    from app.db.session import set_founder_rls_context
                    set_founder_rls_context(session, self._founder_uuid)
                session.add(row)
                session.commit()
            finally:
                closer = getattr(session, "close", None)
                if callable(closer):
                    closer()
        except Exception as exc:  # telemetry must never break the call
            logger.warning("llm_call_log write failed (ignored)", exc_info=exc)
