"""ReasoningTrigger -- the adapter that runs reasoning on session completion.

Implements the diagnosis module's SessionCompletionNotifier port. It encapsulates
all the reasoning-execution concerns (building the service, driving the async
pipeline, best-effort error handling) so the diagnosis router only ever notifies
completion through the abstraction -- it never invokes reasoning directly.

Best-effort: the session is already completed and committed by the diagnosis
flow, so a reasoning failure is logged and swallowed rather than failing the
founder's answer submission. Reasoning is idempotent, so a failed run can be
retried later without duplicating data.

THIS DOES NOT RUN ON THE REQUEST PATH, and that is the point of the design.
It used to: the notifier was invoked inline from `submit_answer`, so the entire
pipeline -- classification, root cause, confidence, recommendations, report
generation, persist -- executed inside the founder's final POST /diagnosis/answer.
Profiled on a real session that pipeline was 203 seconds. The frontend gives up
at 45s (services/diagnosis.js) and the load balancer in front of the container
cuts the connection well before 203s regardless of which one is in use, so the
request was being severed mid-pipeline as a matter of routine. Because the
failure was caught and swallowed right here, the result was a COMPLETED session
with no report, no error surfaced to anyone, and -- for a founder on a plan with
a lifetime diagnosis cap -- no way to try again without an admin.

It is now scheduled as a Starlette BackgroundTask by the router, which runs it
AFTER the response has been sent, on a threadpool worker rather than the event
loop (Starlette routes sync callables there, which is why this method is
deliberately `def` and not `async def` -- making it async would move a 203-second
blocking pipeline onto the event loop and stall every other request in the
process). `run_sync` still drives the async pipeline from this sync frame, the
same sync-caller/async-provider seam the report narrator uses.

The remaining failure mode is honest and bounded: a background task dies with
the container if the task is replaced mid-run. That is what the reconciliation
sweep is for -- POST /internal/jobs/reconcile-reports finds COMPLETED sessions
with no active report and re-runs them. The sweep is the durability guarantee,
not this.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.reasoning.deps import build_reasoning_service
from app.api.v1.reasoning.errors import ReasoningError
from app.core.logger import logger
from app.db.session import (
    SessionLocal,
    set_admin_rls_context,
    set_founder_rls_context,
)
from app.models import FounderReport
from app.models.diagnosis import DiagnosisSession, Founder
from app.models.enums import SessionStatus
from app.services.llm.text import run_sync


class ReasoningTrigger:
    """Runs the reasoning pipeline once when notified of a completed session.

    Owns its own database session. It used to be handed the request's session and
    run inside it, which was the whole problem: see this module's docstring for
    why the pipeline no longer runs on the request path at all. Opening a session
    here is what lets the caller schedule this and return immediately, and it is
    also required for correctness -- the request's session is closed by the time a
    background task runs.
    """

    def notify_session_completed(
        self, founder_id: int, session_id: int, founder_uuid: str
    ) -> None:
        db = SessionLocal()
        try:
            # Before ANY query. A fresh session carries no RLS context, and the
            # founder-isolation policies resolve through get_founder_id() ->
            # app.current_founder_uuid -- so without this every read below
            # returns zero rows and the pipeline "succeeds" having analysed
            # nothing. Scoped to this founder rather than the policies' admin
            # bypass: this task acts for exactly one founder and should be able
            # to see exactly one founder's data.
            set_founder_rls_context(db, str(founder_uuid))

            founder = db.get(Founder, founder_id)
            if founder is None:
                # Not a transient failure -- nothing to retry. Only reachable if
                # the founder was erased between completing the diagnosis and this
                # task running (the privacy deletion sweep), in which case there is
                # correctly nobody left to generate a report for.
                logger.warning(
                    "reasoning skipped: founder no longer exists",
                    extra={"session_id": session_id, "founder_id": founder_id},
                )
                return
            service = build_reasoning_service(db)
            run_sync(service.analyze_session(founder, session_id))
        except ReasoningError as exc:
            logger.error(
                "background reasoning failed after session completion",
                extra={"session_id": session_id, "founder_id": founder_id},
                exc_info=exc,
            )
        except Exception as exc:  # a background task must not raise into the loop
            logger.error(
                "unexpected background reasoning failure",
                extra={"session_id": session_id, "founder_id": founder_id},
                exc_info=exc,
            )
        finally:
            # This session is not managed by a FastAPI dependency, so nothing else
            # will close it. Leaking one per completed diagnosis would exhaust a
            # pool sized at 2+3 per process within a handful of diagnoses.
            db.close()


def get_reasoning_trigger() -> ReasoningTrigger:
    """Dependency provider bound to the diagnosis completion notifier at
    composition (main.py)."""
    return ReasoningTrigger()


def find_sessions_missing_reports(
    db: Session, *, older_than_minutes: int = 15, limit: int = 25
) -> list[tuple[int, int]]:
    """COMPLETED sessions that have no active report. Returns (founder_id, session_id).

    This is the detectable form of "the background reasoning run never finished":
    the diagnosis committed, the founder's answers are all there, and the report
    that should have followed does not exist. An active founder_reports row is
    already the pipeline's own idempotency signal (ReasoningRepository.
    get_active_report), and the pipeline's writes commit as one transaction, so
    "no active report" means the run did not complete -- never that it half-ran.

    `older_than_minutes` keeps the sweep from racing the very background task it
    exists to back up. A diagnosis that completed ninety seconds ago is probably
    still being reasoned about; picking it up would run the pipeline twice
    concurrently. The second run would be caught by the idempotency guard under
    the persist row-lock rather than corrupting anything, but it would still burn
    a full pipeline's worth of provider calls for nothing.

    `limit` bounds one sweep. A backlog drains over several runs instead of one
    unbounded request that the scheduler's own timeout would cut off partway --
    which would be the same failure this whole change is about, one level up.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    active_report = (
        select(FounderReport.session_id)
        .where(FounderReport.is_active.is_(True))
        .scalar_subquery()
    )
    rows = db.execute(
        select(DiagnosisSession.founder_id, DiagnosisSession.session_id)
        .where(
            DiagnosisSession.status == SessionStatus.COMPLETED,
            DiagnosisSession.completed_at.is_not(None),
            DiagnosisSession.completed_at < cutoff,
            DiagnosisSession.session_id.not_in(active_report),
        )
        .order_by(DiagnosisSession.completed_at.asc())
        .limit(limit)
    ).all()
    return [(r[0], r[1]) for r in rows]


def reconcile_missing_reports(
    db: Session, *, older_than_minutes: int = 15, limit: int = 25
) -> dict:
    """Re-run reasoning for every completed session left without a report.

    The durability half of moving reasoning off the request path. A background
    task dies with its container, so "scheduled and forgotten" is not a guarantee
    on its own -- this is what makes the guarantee, and it covers the older
    failures too (a provider outage, a transient DB error) which previously
    stranded a founder permanently with no self-service way back.

    Idempotent by construction: analyze_session no-ops when an active report
    already exists, so a sweep that overlaps a still-running background task, or
    one that runs twice because the scheduler retried, costs a lookup rather than
    a duplicate report. One session's failure never stops the sweep -- the next
    founder in the backlog should not be punished for the previous one's bad row.
    """
    # This job has no founder identity and legitimately spans founders -- it has
    # to find orphaned sessions before it can know whose they are. Without a
    # context the founder-isolation policies would hide every row and the sweep
    # would report a clean "nothing pending" while founders sat without reports,
    # which is the worst possible failure for a safety net. Transaction-local, so
    # it cannot outlive this request on a pooled connection.
    set_admin_rls_context(db)

    pending = find_sessions_missing_reports(
        db, older_than_minutes=older_than_minutes, limit=limit
    )
    results: list[dict] = []
    for founder_id, session_id in pending:
        founder = db.get(Founder, founder_id)
        if founder is None:
            results.append({"session_id": session_id, "founder_id": founder_id,
                            "status": "skipped", "reason": "founder no longer exists"})
            continue
        try:
            result = run_sync(build_reasoning_service(db).analyze_session(founder, session_id))
        except Exception as exc:  # noqa: BLE001 -- one bad session must not stop the sweep
            logger.error(
                "report reconciliation failed for one session, continuing sweep",
                extra={"session_id": session_id, "founder_id": founder_id},
                exc_info=exc,
            )
            db.rollback()
            results.append({"session_id": session_id, "founder_id": founder_id,
                            "status": "failed", "error": str(exc)})
            continue
        logger.info(
            "report reconciled for a session that had none",
            extra={"session_id": session_id, "founder_id": founder_id,
                   "regenerated": result is not None},
        )
        results.append({
            "session_id": session_id, "founder_id": founder_id,
            "status": "regenerated" if result is not None else "already_present",
        })
    return {"pending_count": len(pending), "results": results}


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
    # Called with the ADMIN's request session, whose RLS context is the admin's
    # own founder uuid (get_founder_record sets it) -- so every read below is for
    # a founder this session cannot see, and each would come back empty. This
    # would have surfaced as a truthful-looking "no such founder" for a founder
    # who plainly exists.
    #
    # Scoped narrowly on purpose: the same gap applies to the admin panel's other
    # cross-founder reads, and widening RLS behaviour across that whole surface is
    # a bigger, separately-reviewed change than this. This is the recovery path
    # for the very failure the background trigger exists to prevent, so it has to
    # work regardless.
    set_admin_rls_context(db)

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
