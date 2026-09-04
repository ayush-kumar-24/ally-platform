"""Internal-only endpoint an external scheduler calls to run the account-
deletion sweep -- the consumer side of deletion_scheduled_at that never
existed before.

Why an HTTP endpoint and not a Celery task: there is no task-queue
infrastructure in this codebase (checked -- no Celery import, no worker
process, no Redis usage anywhere in app/, despite being listed as part of
the intended stack). Building that out is a bigger decision than this one
job justifies. This matches the pattern the RDS migration brief already
assumes for `create_next_month_partitions()` -- "EventBridge + Lambda, or
pg_cron if enabled" calling a plain callable on a schedule -- so a protected
endpoint any of those can hit is the option that doesn't invent new
infrastructure or contradict a decision already being made elsewhere.

No founder is present in this request at all -- authenticated by a shared
secret (X-Internal-Secret / INTERNAL_JOBS_SECRET), not a founder or admin
token. Idempotent: re-running finds nothing new to do, because
find_due_for_deletion() only returns founders whose deletion_executed_at is
still NULL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.db.session import get_db
from app.privacy.db_repository import SqlAlchemyPrivacyRepository
from app.privacy.deletion_executor import AccountDeletionExecutor

router = APIRouter(prefix="/internal/jobs", tags=["internal"])


def _verify_secret(x_internal_secret: str | None) -> None:
    if not settings.INTERNAL_JOBS_SECRET:
        logger.error("internal jobs endpoint called but INTERNAL_JOBS_SECRET is unset")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Internal jobs not configured")
    if not x_internal_secret or x_internal_secret != settings.INTERNAL_JOBS_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal secret")


@router.post("/process-deletions", summary="Run the account-erasure sweep for due founders")
def process_deletions(
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    _verify_secret(x_internal_secret)

    from datetime import datetime, timezone

    repo = SqlAlchemyPrivacyRepository(db)
    executor = AccountDeletionExecutor(db)
    now = datetime.now(timezone.utc)

    due = repo.find_due_for_deletion(now)
    results = []
    for founder_id in due:
        try:
            result = executor.run(founder_id)
            results.append({"founder_id": founder_id, "status": "executed",
                            "tables_touched": len(result.hard_deleted)})
        except Exception as exc:  # noqa: BLE001 -- one founder's failure must not stop the sweep
            logger.error("deletion execution failed for one founder, continuing sweep",
                        extra={"founder_id": founder_id, "error": str(exc)})
            db.rollback()
            results.append({"founder_id": founder_id, "status": "failed", "error": str(exc)})

    return {"due_count": len(due), "results": results}


@router.post(
    "/reconcile-reports",
    summary="Regenerate reports for completed diagnoses that never produced one",
)
def reconcile_reports(
    older_than_minutes: int = 15,
    limit: int = 25,
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """The durability guarantee behind moving reasoning off the request path.

    Reasoning now runs as a background task after the founder's final answer is
    acknowledged, which fixes a 203-second pipeline being cut off by a load
    balancer mid-run -- but a background task still dies with its container. This
    sweep is what makes the outcome recoverable rather than merely faster: it
    finds COMPLETED sessions with no active report and re-runs them.

    It also covers the failures that predate that change and used to strand a
    founder permanently -- a provider outage, a transient DB error during
    persist. Before this existed the only way back was an admin manually calling
    regenerate_report_for_founder, and nothing told anyone it was needed.

    Same shape and same auth as process-deletions above, deliberately: a shared
    secret rather than a founder or admin token, idempotent, and callable by
    whatever already runs that sweep (EventBridge, pg_cron, a plain cron) with no
    new infrastructure. Every 5-10 minutes is a sensible cadence -- often enough
    that a founder waiting on the Thinking screen is likely still there when the
    report lands, rare enough not to trip the older_than_minutes guard.
    """
    _verify_secret(x_internal_secret)

    from app.api.v1.reasoning.trigger import reconcile_missing_reports

    return reconcile_missing_reports(
        db, older_than_minutes=older_than_minutes, limit=limit
    )


@router.post(
    "/backfill-report-pdfs",
    summary="Render the report PDFs founders are waiting on",
)
def backfill_report_pdfs(
    limit: int = 25,
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """What makes "your PDF will be ready in a few minutes" a promise.

    A download that could not be rendered (Gotenberg unreachable) no longer
    returns a substitute document -- it tells the founder honestly and stamps
    `founder_reports.pdf_requested_at`. This sweep is the other half: it renders
    exactly those, stores them, and clears the flag, so the founder's next
    attempt is served from storage instantly.

    Only reports someone actually asked for. Most reports are never downloaded,
    and pre-rendering all of them would spend Chromium time on documents nobody
    opens.

    Same shape and same auth as the two sweeps above -- shared secret,
    idempotent, callable by whatever cron already runs them. Every 5-10 minutes
    alongside reconcile-reports is the sensible cadence; the whole point is that
    a founder who was told "a few minutes" is not waiting on a human.
    """
    _verify_secret(x_internal_secret)

    from app.api.v1.reports.pdf_delivery import backfill_pending_pdfs

    return backfill_pending_pdfs(db, limit=limit)


@router.post(
    "/check-health",
    summary="Run the system health check and alert if it just turned red",
)
def check_health(
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Admin Panel Proposal Phase 3's other half: `GET /admin/health` (the
    panel page) is pull-based and never itself alerts anyone -- this is the
    push side. Same shape and same auth as the sweeps above: shared secret,
    callable by whatever cron/EventBridge/pg_cron already runs them.

    Alerts only on a green -> red transition (see HealthAlertService), so
    running this every few minutes during a real outage sends one email, not
    one every few minutes -- and the response always reports the true
    current status regardless of whether an alert fired.
    """
    _verify_secret(x_internal_secret)

    from app.core.container import container

    report = container.health_checker(db).check()
    alerted = container.health_alert_service().notify(report)

    return {
        "status": report.status.value,
        "components": [
            {"key": c.key, "label": c.label, "status": c.status.value, "detail": c.detail}
            for c in report.components
        ],
        "checked_at": report.checked_at.isoformat(),
        "alert_sent": alerted,
    }


@router.post(
    "/send-reminders",
    summary="Deliver due task reminders and discovery-call reminders",
)
def send_reminders(
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Both reminder queues, in one sweep.

    They are separate systems -- planning_reminders is a founder scheduling a
    nudge on their own task, discovery_calls is our own 24h/1h call reminder --
    but they answer to the same schedule and the same failure mode, so one
    endpoint means one cron entry and one place to look when mail goes quiet.

    Idempotent: each side only selects rows it has not marked sent, so a re-run
    (or an overlapping run) finds nothing new rather than mailing twice.

    The two are isolated from each other on purpose. Discovery reminders are
    transactional and unrelated to any plan; letting a failure in the task
    sweep cancel them would take out a call reminder over an unrelated bug.
    """
    _verify_secret(x_internal_secret)

    from app.services.discovery_notifications import send_due_reminders
    from app.services.reminder_dispatch import send_due_task_reminders

    out: dict = {}
    for key, run in (("tasks", send_due_task_reminders), ("calls", send_due_reminders)):
        try:
            out[key] = run(db)
        except Exception as exc:  # noqa: BLE001 -- one queue must not take out the other
            logger.error("reminder sweep failed for one queue, continuing",
                         extra={"queue": key, "error": str(exc)})
            db.rollback()
            out[key] = {"error": str(exc)}
    return out
