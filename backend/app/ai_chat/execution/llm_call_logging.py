"""Chat-path LLM call telemetry -- the `llm_call_log` table has always recorded
every reasoning-pipeline LLM call (via `services.llm.telemetry.LoggingLLMProvider`)
but never a single chat-path call, because the chat orchestrator's provider chain
(`app.integrations.llm`) speaks a different, vendor-neutral request/response shape
than the reasoning side and was never wrapped the same way. Confirmed live: after a
real, successful chat turn (200 OK, real Anthropic response), `llm_call_log` had
zero new rows for that founder even 15 minutes later.

This does the same job as `LoggingLLMProvider`, but from `ChatExecutionService`
instead of from inside a provider decorator -- because founder/session identity
lives at the chat-execution layer, not the provider layer, and `AIRequest`/
`AIResponse` are deliberately founder-agnostic (see their docstrings). Wrapping the
provider chain itself would mean threading founder_id/session_id through a layer
that's explicitly designed never to know about them.

Writing the log must NEVER break the chat turn it describes: on any error here
(bad session, DB unavailable, whatever) we log a warning and swallow -- same
fail-open convention as everywhere else in this codebase (memory, retrieval,
graph). A missing telemetry row is an observability gap; a broken chat turn is a
product outage. Never trade the second for the first.
"""

from __future__ import annotations

from app.api.v1.ally.execution.schemas import AIResponse
from app.core.logger import logger
from app.models.llm import LLMCallLog
from app.services.llm.telemetry import estimate_cost

CHAT_TASK = "ally_chat"


def record_chat_llm_call(
    ai: AIResponse,
    *,
    founder_id: int,
    session_id: int | None,
    latency_ms: int,
    task: str = CHAT_TASK,
    session_factory=None,
) -> None:
    """Write one `llm_call_log` row for a completed (or failed) chat turn's AI
    execution step. Mirrors `LoggingLLMProvider._log` exactly -- own short-lived
    DB session, swallow-and-log on any failure, never raise."""
    provider = ai.metadata.provider if ai.metadata is not None else "unknown"
    model_id = ai.metadata.model if ai.metadata is not None else "unknown"
    status = "ok" if ai.ok else "error"

    row = LLMCallLog(
        task=task,
        provider=provider,
        model_id=model_id,
        status=status,
        input_tokens=ai.token_usage.prompt_tokens if ai.ok else None,
        output_tokens=ai.token_usage.completion_tokens if ai.ok else None,
        latency_ms=latency_ms,
        estimated_cost_usd=(
            estimate_cost(
                model_id, ai.token_usage.prompt_tokens, ai.token_usage.completion_tokens
            )
            if status == "ok"
            else None
        ),
        founder_id=founder_id,
        session_id=session_id,
        error=(ai.error[:500] if ai.error else None) if not ai.ok else None,
    )

    factory = session_factory
    if factory is None:
        from app.db.session import SessionLocal  # lazy: own short-lived session

        factory = SessionLocal
    try:
        session = factory()
        try:
            session.add(row)
            session.commit()
        finally:
            closer = getattr(session, "close", None)
            if callable(closer):
                closer()
    except Exception as exc:  # noqa: BLE001 -- telemetry must never break the turn
        logger.warning("chat llm_call_log write failed (ignored)", exc_info=exc)
