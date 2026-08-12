"""ReasoningTrigger -- the adapter that runs reasoning on session completion.

Implements the diagnosis module's SessionCompletionNotifier port. It encapsulates
all the reasoning-execution concerns (building the service, driving the async
pipeline, best-effort error handling) so the diagnosis router only ever notifies
completion through the abstraction -- it never invokes reasoning directly.

Best-effort: the session is already completed and committed by the diagnosis
flow, so a reasoning failure is logged and swallowed rather than failing the
founder's answer submission. Reasoning is idempotent, so a failed run can be
retried later without duplicating data.

`submit_answer` (the diagnosis router's answer endpoint) is `async def`, so this
runs on FastAPI's live event loop, not a worker thread -- a bare `asyncio.run`
here would raise "cannot be called from a running event loop" and silently
drop every reasoning run (confirmed live: a completed session with 30 real
answers produced zero founder_reports/detected_root_causes rows). `run_sync`
(already used by the report narrator for the identical sync-caller/async-
provider seam) detects the running loop and drives the pipeline to completion
on a short-lived worker thread instead.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.v1.reasoning.deps import build_reasoning_service
from app.api.v1.reasoning.errors import ReasoningError
from app.core.logger import logger
from app.models.diagnosis import Founder
from app.services.llm.text import run_sync


class ReasoningTrigger:
    """Runs the reasoning pipeline once when notified of a completed session."""

    def notify_session_completed(
        self, db: Session, founder: Founder, session_id: int
    ) -> None:
        service = build_reasoning_service(db)
        try:
            run_sync(service.analyze_session(founder, session_id))
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
