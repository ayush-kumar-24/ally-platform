"""Task reminders by email -- the delivery half of `planning_reminders`.

WHAT WAS MISSING. The reminders table, the `POST /tasks/{id}/reminders`
endpoint, `due_reminders()` and `mark_reminder_sent()` all shipped with Plan
Your Day. Nothing ever called the last two. Reminders were written and never
read, so a row sat at status "scheduled" forever and no founder was ever
reminded of anything -- while Billing sold "Email reminders from Ally" as a Pro
feature. This module is the consumer that was never written, plus the scheduler
that puts rows in the table in the first place (until now, only a founder
calling the endpoint by hand could create one, and no client ever did).

TWO HALVES, DELIBERATELY SEPARATE:

  `sync_for_task`      runs in the request, after a task is saved. Cheap: it
                       computes a time and writes at most one row. It NEVER
                       sends anything, so a mail outage cannot fail a save.
  `send_due_reminders` runs in a scheduled job. It sends, and marks sent.

WHY THE TIMING MIRRORS THE CALENDAR. A founder with Google Calendar connected
already gets a popup at CALENDAR_REMINDER_MINUTES_BEFORE. If this email fired
at a different offset, that founder would be nudged twice about one task at two
unrelated moments. TASK_REMINDER_MINUTES_BEFORE defaults to the same 30, and a
task with a date but no time uses CALENDAR_DEFAULT_TASK_HOUR -- the same 9am the
calendar path picks, and for the same reason: an offset counted back from
midnight lands at 23:30 the night before.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.models import Founder
from app.planning.models import (
    ProgressStatus,
    Reminder,
    ReminderChannel,
    Task,
)
from app.planning.service import PlanningService
from app.plans.catalog import Feature
from app.services.email import send_email

#: Where the email points. One link, to the page the task lives on.
_PLAN_URL = "https://app.goxlally.ai/app/plan"


def _zone(timezone_name: str) -> ZoneInfo:
    """The founder's zone, or UTC if they sent us something unusable.

    A bad IANA name comes from the browser and is not worth failing a save
    over -- the reminder lands at the wrong hour, which is visible and
    fixable; a 500 on adding a task is neither.
    """
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("task reminder: unknown timezone, falling back to UTC",
                       extra={"path": f"timezone={timezone_name!r}"})
        return ZoneInfo("UTC")


def reminder_time_for(due_date: date | None, due_time: time | None,
                      timezone_name: str = "UTC") -> datetime | None:
    """When to email about a task due at this date/time, as a UTC instant.

    None when the task has no due date -- there is nothing to count backwards
    from, and a task with no date is a list item, not an appointment.
    """
    if due_date is None:
        return None
    local = datetime.combine(
        due_date, due_time or time(hour=settings.CALENDAR_DEFAULT_TASK_HOUR),
        tzinfo=_zone(timezone_name))
    due_utc = local.astimezone(timezone.utc)
    return due_utc - timedelta(minutes=settings.TASK_REMINDER_MINUTES_BEFORE)


def sync_for_task(service: PlanningService, task: Task, *,
                  timezone_name: str = "UTC") -> Reminder | None:
    """Keep the task's AUTO email reminder in step with its due date.

    Call after every task save. Returns the live reminder, or None when there
    is nothing to remind about. Never raises: a reminder that fails to schedule
    must not cost the founder the task they just typed, which is the same rule
    the calendar hook next door follows.
    """
    try:
        return service.sync_task_reminder(
            task.founder_id, task,
            remind_at=reminder_time_for(task.due_date, task.due_time, timezone_name),
            channel=ReminderChannel.EMAIL,
        )
    except Exception as exc:
        logger.warning("task reminder sync failed",
                       extra={"founder_id": task.founder_id, "task_id": task.task_id},
                       exc_info=exc)
        return None


# --- the email --------------------------------------------------------------

def _when_phrase(remind_at: datetime, due_at: datetime, tz: str) -> str:
    minutes = max(0, round((due_at - remind_at).total_seconds() / 60))
    local = due_at.astimezone(_zone(tz))
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        lead = f"in {hours} hour{'s' if hours > 1 else ''}"
    elif minutes:
        lead = f"in {minutes} minutes"
    else:
        lead = "now"
    return f"{lead} -- {local.strftime('%A, %d %B at %I:%M %p')}"


def send_task_reminder(to: str, name: str, title: str, when: str,
                       note: str = "") -> bool:
    """One reminder email for one task."""
    subject = f"Reminder: {title}"
    note_text = f"\nYour note: {note}\n" if note else ""
    text = (
        f"Hi {name},\n\n"
        f"\"{title}\" is due {when}.\n"
        f"{note_text}\n"
        f"Open Plan Your Day: {_PLAN_URL}\n\n"
        "If it is done, tick it off and this is the last you will hear about it.\n\n"
        "The GoXL Team\n\n"
        "--\n"
        "To stop these, turn off task reminder emails in Profile > Notifications."
    )
    # escape(): the title is whatever the founder typed. An ampersand in a task
    # name should not break the markup of their own reminder.
    safe_note = (f"<p><em>Your note: {escape(note)}</em></p>" if note else "")
    html = (
        f"<p>Hi {escape(name)},</p>"
        f"<p><strong>{escape(title)}</strong> is due {escape(when)}.</p>"
        f"{safe_note}"
        f'<p><a href="{_PLAN_URL}">Open Plan Your Day</a></p>'
        f"<p>If it is done, tick it off and this is the last you will hear about it.</p>"
        f"<p>The GoXL Team</p>"
        f'<p style="color:#6b7280;font-size:12px">To stop these, turn off task '
        f"reminder emails in Profile &gt; Notifications.</p>"
    )
    return send_email(to, subject, text, html)


# --- the worker -------------------------------------------------------------

def _wants_task_reminders(founder: Founder) -> bool:
    """Opt-out, defaulting to on.

    A DEDICATED FLAG, not `email_reminders`. That one is read by
    discovery_notifications to gate the reminder for a call the founder paid
    for, and the profile switch is labelled "Call reminders by email" for
    exactly that reason. Reusing it would mean someone silencing task nags also
    silences the reminder for their call -- the same conflation that was fixed
    when the switch was relabelled.
    """
    prefs = founder.notification_preferences or {}
    return bool(prefs.get("email_task_reminders", True))


def send_due_reminders(db: Session, *, now: datetime | None = None) -> dict:
    """Send every email reminder that has come due. Call from a scheduled job.

    HOW OFTEN THIS MUST RUN. Every 15 minutes. The reminder is scheduled for a
    specific minute, and this only sends rows already past it, so the founder's
    nudge is late by however long the gap between runs is. Fifteen minutes of
    lateness on a 30-minute warning is tolerable; an hour is not.

    STALE ROWS ARE DROPPED, NOT SENT. If the job stops for a day, every reminder
    that came due meanwhile is still sitting at "scheduled". Sending them on
    recovery means a founder opens their inbox to twenty emails about tasks that
    were due yesterday -- so anything older than TASK_REMINDER_MAX_AGE_MINUTES is
    marked sent without an email. It is counted separately (`stale`) precisely
    so that a scheduler's logs show the outage instead of hiding it in a
    cheerful "sent: 0".

    EVERY ROW IS MARKED, WHATEVER HAPPENS. Skipped for plan, skipped for
    preference, task deleted, stale -- all of them move off "scheduled". A row
    left behind is re-examined on every run for the rest of time, and the first
    real failure would be re-sent every fifteen minutes forever.

    Returns counts for observability.
    """
    from app.core.container import container

    now = now or datetime.now(timezone.utc)
    counts = {"sent": 0, "skipped_pref": 0, "skipped_plan": 0,
              "stale": 0, "orphaned": 0, "failed": 0}

    service: PlanningService = container.planning_service(db)
    entitlements = container.entitlement_service(db)
    cutoff = now - timedelta(minutes=settings.TASK_REMINDER_MAX_AGE_MINUTES)

    for reminder in service.due_reminders(before=now):
        if reminder.channel != ReminderChannel.EMAIL:
            continue                                   # in_app rows are the bell's business
        try:
            _deliver_one(db, service, entitlements, reminder, counts, cutoff)
        except Exception as exc:
            # One founder's bad row must not stop the other founders' reminders.
            counts["failed"] += 1
            logger.error("task reminder failed",
                         extra={"founder_id": reminder.founder_id,
                                "path": f"reminder_id={reminder.reminder_id}"},
                         exc_info=exc)
    db.commit()
    return counts


def _deliver_one(db: Session, service: PlanningService, entitlements,
                 reminder: Reminder, counts: dict, cutoff: datetime) -> None:
    task = service.repository.get_task(reminder.task_id)
    founder = db.get(Founder, reminder.founder_id)

    # The task was deleted, or the founder was. Nothing to remind anyone about;
    # the row is closed out rather than retried forever.
    if task is None or founder is None or not founder.email:
        counts["orphaned"] += 1
        service.mark_reminder_sent(reminder.reminder_id)
        return

    # Finished between scheduling and now. The sync cancels the reminder when a
    # task is ticked off, but only if the task was saved through the API -- this
    # is the backstop for every other path that can set DONE.
    if task.status == ProgressStatus.DONE:
        counts["orphaned"] += 1
        service.mark_reminder_sent(reminder.reminder_id)
        return

    if reminder.remind_at < cutoff:
        counts["stale"] += 1
        service.mark_reminder_sent(reminder.reminder_id)
        return

    # Sold as Pro on the pricing page (Feature.EMAIL_NOTIFICATIONS lives in the
    # advisor bundle), so it is checked here rather than at scheduling time: a
    # founder who upgrades should start getting the reminders already sitting in
    # the table, and one who downgrades should stop.
    if not entitlements.has_feature(founder.plan_type, Feature.EMAIL_NOTIFICATIONS):
        counts["skipped_plan"] += 1
        service.mark_reminder_sent(reminder.reminder_id)
        return

    if not _wants_task_reminders(founder):
        counts["skipped_pref"] += 1
        service.mark_reminder_sent(reminder.reminder_id)
        return

    due_at = reminder.remind_at + timedelta(minutes=settings.TASK_REMINDER_MINUTES_BEFORE)
    when = _when_phrase(reminder.remind_at, due_at,
                        getattr(founder, "timezone", None) or settings.DISCOVERY_TIMEZONE)
    send_task_reminder(founder.email, founder.full_name or "there",
                       task.title, when, reminder.note)
    counts["sent"] += 1
    service.mark_reminder_sent(reminder.reminder_id)
