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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.reasoning.deps import build_reasoning_service
from app.api.v1.reasoning.errors import ReasoningError
from app.core.logger import logger
from app.models.diagnosis import DiagnosisSession, Founder
from app.models.enums import SessionStatus
from app.services.llm.text import run_sync


class ReasoningTrigger:
    """Runs the reasoning pipeline once when notified of a completed session."""

    def notify_session_completed(
        self, db: Session, founder: Founder, session_id: int
    ) -> None:
        try:
            service = build_reasoning_service(db)
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


def regenerate_report_for_founder(db: Session, founder_id: int) -> dict:
    """Recovery path for the case notify_session_completed's docstring warns
    about: the founder's session completed and was committed, but the
    best-effort reasoning run that should have followed it failed (LLM
    hiccup, transient error) and nothing retried it. Before this existed,
    that founder was permanently stranded -- COMPLETED session, no report,
    no self-service or admin way to get one, and (for a free-tier founder)
    their one lifetime diagnosis allowance already spent.

    Wired as AdminPanelService.report_regenerator -- see container.py. Finds
    the founder's most recent completed session and re-runs the reasoning
    pipeline with force=True, bypassing analyze_session's normal
    already-has-a-report no-op (this IS the "there's no report, make one"
    path). Reasoning is idempotent/transactional (analyze_session rolls back
    its own failures), so this is safe to call again if it fails again.
    """
    founder = db.get(Founder, founder_id)
    if founder is None:
        return {"status": "not_found", "reason": "no such founder"}

    session_id = db.execute(
        select(DiagnosisSession.session_id)
        .where(
            DiagnosisSession.founder_id == founder_id,
            DiagnosisSession.status == SessionStatus.COMPLETED,
        )
        .order_by(DiagnosisSession.updated_at.desc())
        .limit(1)
    ).scalar()
    if session_id is None:
        return {"status": "not_found", "reason": "no completed diagnosis session for this founder"}

    try:
        service = build_reasoning_service(db)
        result = run_sync(service.analyze_session(founder, session_id, force=True))
    except ReasoningError as exc:
        logger.error(
            "admin-triggered report regeneration failed",
            extra={"founder_id": founder_id, "session_id": session_id},
            exc_info=exc,
        )
        return {"status": "failed", "session_id": session_id, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 -- surface to the admin, don't 500 the panel
        logger.error(
            "admin-triggered report regeneration failed unexpectedly",
            extra={"founder_id": founder_id, "session_id": session_id},
            exc_info=exc,
        )
        return {"status": "failed", "session_id": session_id, "error": str(exc)}

    return {
        "status": "regenerated" if result is not None else "no_change",
        "session_id": session_id,
        "report_id": getattr(result, "report_id", None) if result is not None else None,
    }
