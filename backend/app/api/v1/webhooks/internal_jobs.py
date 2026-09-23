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
from app.db.session import get_db, set_admin_rls_context
from app.privacy.db_repository import SqlAlchemyPrivacyRepository
from app.privacy.deletion_executor import AccountDeletionExecutor

router = APIRouter(prefix="/internal/jobs", tags=["internal"])


def _verify_secret(x_internal_secret: str | None) -> None:
    if not settings.INTERNAL_JOBS_SECRET:
        logger.error("internal jobs endpoint called but INTERNAL_JOBS_SECRET is unset")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Internal jobs not configured")
    if not x_internal_secret or x_internal_secret != settings.INTERNAL_JOBS_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal secret")


def authorise_internal_job(
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    """Check the shared secret, then tell the database this is a system actor.

    THE TWO ARE DELIBERATELY WELDED TOGETHER. Every job here works across ALL
    founders by definition -- that is what a sweep is -- and the docstring at
    the top of this module already says no founder is present in the request.
    But every table these jobs read is founder-scoped under row-level security
    (migration d91c6e4b72aa), whose policy is
    `founder_id = get_founder_id() OR app.current_admin`.

    With neither set, `get_founder_id()` is NULL and the policy hides every
    row. So in production these jobs found NOTHING and reported success:
    find_due_for_deletion() returned an empty list, the sweep logged zero
    erasures, and a founder who asked to be deleted was never deleted -- with
    a green run every day saying otherwise. Reports were never reconciled and
    call reminders never sent, for the same reason.

    Invisible in local development, which connects as a BYPASSRLS superuser
    and never exercises the policy at all.

    Coupled into one dependency rather than left as two calls so the next job
    added to this file cannot authenticate correctly and still sweep nothing.
    Set with is_local = true, so it dies with this request's transaction.

    ORDER MATTERS. The secret is checked FIRST: widening row-level security is
    the privilege this endpoint's shared secret authorises, so it must be
    unreachable by anyone who has not presented it.
    """
    _verify_secret(x_internal_secret)
    set_admin_rls_context(db)


@router.post("/process-deletions", summary="Run the account-erasure sweep for due founders")
def process_deletions(
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
) -> dict:

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

    executed = sum(1 for r in results if r["status"] == "executed")
    failed = len(results) - executed

    # THE HEARTBEAT. Exactly one line per sweep, and unconditionally -- a run
    # that found nobody due has to say so, or the CloudWatch alarm watching for
    # the ABSENCE of this line fires on a perfectly healthy job. Which is the
    # more useful signal precisely because the failure it guards against is a
    # job that stops running: a job that does not run produces no output, so
    # nothing but an expected line going missing can catch it.
    #
    # `failed` is worth an alarm of its own. Those founders asked to be erased
    # and have not been; they are retried on the next sweep, but a number that
    # does not come back down is a schema problem somebody has to look at.
    logger.info(
        "deletion sweep completed",
        extra={"due_count": len(due), "executed_count": executed,
               "failed_count": failed},
    )

    return {"due_count": len(due), "executed_count": executed,
            "failed_count": failed, "results": results}


@router.post(
    "/reconcile-reports",
    summary="Regenerate reports for completed diagnoses that never produced one",
)
def reconcile_reports(
    older_than_minutes: int = 15,
    limit: int = 25,
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
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
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
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

    from app.api.v1.reports.pdf_delivery import backfill_pending_pdfs

    return backfill_pending_pdfs(db, limit=limit)


@router.post(
    "/check-health",
    summary="Run the system health check and alert if it just turned red",
)
def check_health(
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
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
    "/send-call-reminders",
    summary="Send any due 24h / 1h discovery-call reminders",
)
def send_call_reminders(
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
) -> dict:
    """The consumer side of `send_due_reminders`, which had no caller at all.

    The reminder logic has existed since discovery calls shipped and nothing
    ever ran it, so the 24h and 1h reminders have never fired for anybody --
    including founders who paid for the call. Same shape and same auth as the
    sweeps above, so whatever cron / EventBridge / pg_cron already runs them
    can run this too.

    **Call this every 15 minutes.** The windows are "within 24h" and "within
    1h", and each call carries a `reminder_sent_24h` / `reminder_sent_1h` flag
    that is set once, so running it more often is harmless (idempotent) and
    running it rarely means a founder gets the 1h reminder late or not at all.

    Note this does nothing useful until EMAIL_HOST is configured -- send_email
    runs in stub mode until then, logging instead of sending. The response
    reports `email_configured` so a scheduler's logs make that obvious rather
    than showing a cheerful zero.
    """

    from app.services.discovery_notifications import send_due_reminders

    result = send_due_reminders(db)
    return {**result, "email_configured": settings.email_enabled}


@router.post(
    "/send-task-reminders",
    summary="Send any due Plan Your Day task reminders by email",
)
def send_task_reminders(
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
) -> dict:
    """The consumer side of `planning_reminders`, which had no caller at all.

    The reminders table, the endpoint that writes to it, `due_reminders()` and
    `mark_reminder_sent()` all shipped with Plan Your Day and nothing ever ran
    them -- so a scheduled reminder sat at status "scheduled" forever and no
    founder was ever emailed about a task. Same shape and same auth as the
    sweeps above, so whatever cron / EventBridge / pg_cron already runs them can
    run this too.

    **Call this every 1-2 minutes.** Reminders are scheduled to the minute and
    only sent once past it, so the founder's nudge is late by however long the
    gap between runs is -- and the founder now picks that offset themselves in
    Plan Your Day, where the smallest is five minutes. A fifteen-minute sweep
    would deliver a "5 minutes before" reminder ten minutes AFTER the task was
    due, which the staleness check then discards, leaving the founder with the
    silence this endpoint exists to end. Idempotent: every row examined moves
    off "scheduled", whether it was sent, skipped or dropped, so re-running
    immediately does nothing.

    See docs/TASK-REMINDER-SCHEDULE.md for the EventBridge Scheduler setup.
    The GitHub Actions sweep still calls this too, but only as a backstop:
    its schedule is best-effort and measured at two-to-five hour gaps.

    Note this does nothing useful until EMAIL_HOST is configured -- send_email
    runs in stub mode until then, logging instead of sending. The response
    reports `email_configured` so a scheduler's logs make that obvious rather
    than showing a cheerful zero.

    THE SAME COUNTS ARE ALSO LOGGED, not just returned. EventBridge Scheduler
    does not record a target's response body anywhere, so returning these
    numbers told the scheduler nothing it could alarm on -- a run that sent
    nothing and a run that dropped forty reminders as stale both looked like
    one successful invocation. The log line below is what CloudWatch metric
    filters read, and the two alarms that matter hang off it:

      * `stale` above zero for any sustained period -- reminders are coming
        due faster than this endpoint is called, i.e. the schedule is not
        keeping up and founders are getting silence.
      * `email_configured` false -- EMAIL_HOST is unset on the backend, so no
        email can go out however often this runs.

    JSONFormatter promotes every `extra` key to a top-level field (see
    core/logger.py), so each count lands as its own filterable JSON field
    rather than inside a formatted string. Keys must therefore stay clear of
    the reserved LogRecord attribute names -- `sent`, `stale` and the rest are,
    and logging would raise on a collision rather than fail quietly.
    """

    from app.services.task_reminders import send_due_reminders

    result = {**send_due_reminders(db), "email_configured": settings.email_enabled}
    logger.info("task reminder job complete", extra=result)
    return result


@router.post(
    "/assign-daily-quotes",
    summary="Choose every founder's two dashboard lines for today",
)
def assign_daily_quotes_job(
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
) -> dict:
    """The midnight sweep behind the quote cards on Compass and Plan Your Day.

    **Call this once a day, at 00:00 IST**, from EventBridge Scheduler -- not
    from the GitHub Actions sweep, whose own workflow comment records its runs
    landing two to five hours apart. A quote that arrives at 3am is fine; one
    that arrives at 3pm changes the card under a founder mid-afternoon, which
    is the thing the whole design exists to prevent.

    Safe to call at any other time, and safe to call twice. A founder who
    already has today's two lines is skipped before any model call is made, and
    every write is first-write-wins, so a late manual run fills in whoever is
    missing without disturbing anyone who is already served.

    WATCH `by_fallback`. A fallback pick is invisible on the page by design --
    it comes from the same shortlist, it is stable for the day, it looks like
    any other line. Which means a provider that has been failing all week looks
    exactly like one that is working, and this number is the only place the
    difference shows. `by_model` at zero with `founders` in the dozens means
    the OpenAI key, the routing row or DAILY_QUOTES_LLM is not what you think
    it is.

    The counts are logged as well as returned, for the same reason the task
    reminder sweep logs its own: EventBridge records nothing of a target's
    response body, so a number that is only returned is a number nobody can
    alarm on.
    """

    from app.quotes.jobs import assign_daily_quotes

    result = assign_daily_quotes(db)
    return result


@router.post(
    "/send-notification-emails",
    summary="Email any bell notifications not yet emailed (Pro founders only)",
)
def send_notification_emails(
    db: Session = Depends(get_db),
    _: None = Depends(authorise_internal_job),
) -> dict:
    """The email leg of the notification system, which never had one.

    All eighteen notification types were written to `notifications` and shown in
    the bell, and that was the end of it -- a founder who did not open the app
    learned nothing. This sweeps the rows `notify()` wrote and mails them to
    founders whose plan includes Feature.EMAIL_NOTIFICATIONS. Same shape and
    same auth as the sweeps above.

    **Call this every 15 minutes.** Idempotent: every row examined gets
    `sent_at` stamped, whether it was sent, skipped or dropped, so re-running
    immediately does nothing. Rows over the per-founder cap are left unstamped
    on purpose and go out on the next run.

    Note this does nothing useful until EMAIL_HOST is configured -- send_email
    runs in stub mode until then, logging instead of sending. The response
    reports `email_configured` so a scheduler's logs make that obvious rather
    than showing a cheerful zero.
    """

    from app.services.notification_emails import send_pending_notification_emails

    result = send_pending_notification_emails(db)
    return {**result, "email_configured": settings.email_enabled}
