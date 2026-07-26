"""ReasoningTrigger -- the adapter that runs reasoning on session completion.

Implements the diagnosis module's SessionCompletionNotifier port. It encapsulates
all the reasoning-execution concerns (building the service, driving the async
pipeline, best-effort error handling) so the diagnosis router only ever notifies
completion through the abstraction -- it never invokes reasoning directly.

Best-effort: the session is already completed and committed by the diagnosis
flow, so a reasoning failure is logged and swallowed rather than failing the
founder's answer submission. Reasoning is idempotent, so a failed run can be
retried later without duplicating data.

The diagnosis endpoint is a synchronous FastAPI path operation (run in a worker
thread), so `asyncio.run` safely drives the async pipeline to completion here.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.api.v1.reasoning.deps import build_reasoning_service
from app.api.v1.reasoning.errors import ReasoningError
from app.core.logger import logger
from app.models.diagnosis import Founder


class ReasoningTrigger:
    """Runs the reasoning pipeline once when notified of a completed session."""

    def notify_session_completed(
        self, db: Session, founder: Founder, session_id: int
    ) -> None:
        service = build_reasoning_service(db)
        try:
            asyncio.run(service.analyze_session(founder, session_id))
        except ReasoningError as exc:
            logger.error(
                "inline reasoning failed after session completion",
                extra={"session_id": session_id, "founder_id": founder.founder_id},
                exc_info=exc,
            )
        except Exception as exc:  # never break the answer response on failure
            logger.error(
                "unexpected inline reasoning failure",
                extra={"session_id": session_id, "founder_id": founder.founder_id},
                exc_info=exc,
            )


def get_reasoning_trigger() -> ReasoningTrigger:
    """Dependency provider bound to the diagnosis completion notifier at
    composition (main.py)."""
    return ReasoningTrigger()
