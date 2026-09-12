"""Task reminders by email -- the delivery half of `planning_reminders`.

WHAT WAS MISSING. The reminders table, the `POST /tasks/{id}/reminders`
endpoint, `due_reminders()` and `mark_reminder_sent()` all shipped with Plan
Your Day. Nothing ever called the last two. Reminders were written and never
read, so a row sat at status "scheduled" forever and no founder was ever
reminded of anything -- while Billing sold "Email reminders from Ally" as a Pro
feature. This module is the consumer that was never written, plus the scheduler
that puts rows in the table in the first place (until now, only a founder
calling the endpoint by hand could create one, and no client ever did).

WHAT THE EMAIL IS, AS OF 2026-09-11. It is a CONFIRMATION sent the moment a
task is given a date, not a nudge thirty minutes before it. The thirty-minute
warning is covered twice over already -- the Google Calendar popup and the
in-app bell -- and a third copy in the inbox at the same minute was noise.

It also has to work, which the old shape did not. The T-30 email depended on a
sweep that GitHub Actions was supposed to run every ten minutes and actually
ran every two to five hours (measured 2026-09-11: 21:09, 23:10, 01:10, 06:05,
11:14 UTC). Anything more than TASK_REMINDER_MAX_AGE_MINUTES past its moment is
dropped rather than sent late, so most reminders were silently discarded while
the job reported a green run. Sending at save time takes the scheduler out of
the path entirely: the email goes out in the same request that created the
task, in a background task so a slow SMTP handshake cannot slow the save.

The old T-30 path is left standing but no longer fed -- `sync_for_task` now
cancels rather than schedules, and `send_due_reminders` below still works if
anyone ever wants it back.

TWO HALVES, DELIBERATELY SEPARATE:

  `notify_task_scheduled` runs in the request, after a task is saved. It
                       decides whether this founder gets an email and returns
                       the work to do; it never sends inline.
  `sync_for_task`      keeps the legacy T-30 row in step -- which now means
                       cancelling it. It NEVER sends anything, so a mail
                       outage cannot fail a save.
  `send_due_reminders` runs in a scheduled job. It sends, and marks sent.
                       Nothing feeds it any more.

WHY THE TIMING MIRRORS THE CALENDAR. A founder with Google Calendar connected
already gets a popup at their chosen offset. If this email fired at a different
one, that founder would be nudged twice about one task at two unrelated
moments. So both read the SAME number: the task's own
`reminder_minutes_before`, chosen in Plan Your Day, falling back to
TASK_REMINDER_MINUTES_BEFORE / CALENDAR_REMINDER_MINUTES_BEFORE (both 30) for a
task created before the picker existed. A task with a date but no time uses
CALENDAR_DEFAULT_TASK_HOUR -- the same 9am the calendar path picks, and for the
same reason: an offset counted back from midnight lands at 23:30 the night
before.
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


def lead_minutes_for(task: Task | None) -> int:
    """How far ahead of a task its reminder goes, in minutes.

    The founder's own choice when they made one, and the platform default when
    they did not -- which is every task created before the picker existed, so
    this is what keeps their behaviour unchanged. 0 is a choice, not a missing
    value, which is why this tests for None rather than falsiness.
    """
    chosen = getattr(task, "reminder_minutes_before", None)
    return settings.TASK_REMINDER_MINUTES_BEFORE if chosen is None else chosen


def reminder_time_for(due_date: date | None, due_time: time | None,
                      timezone_name: str = "UTC",
                      lead_minutes: int | None = None) -> datetime | None:
    """When to email about a task due at this date/time, as a UTC instant.

    None when the task has no due date -- there is nothing to count backwards
    from, and a task with no date is a list item, not an appointment.

    `lead_minutes` is the founder's per-task choice; None falls back to
    TASK_REMINDER_MINUTES_BEFORE so a caller that has no task in hand still
    gets the old behaviour.
    """
    if due_date is None:
        return None
    if lead_minutes is None:
        lead_minutes = settings.TASK_REMINDER_MINUTES_BEFORE
    local = datetime.combine(
        due_date, due_time or time(hour=settings.CALENDAR_DEFAULT_TASK_HOUR),
        tzinfo=_zone(timezone_name))
    due_utc = local.astimezone(timezone.utc)
    return due_utc - timedelta(minutes=lead_minutes)


def sync_for_task(service: PlanningService, task: Task, *,
                  timezone_name: str = "UTC") -> Reminder | None:
    """Close out the task's legacy T-30 email reminder.

    Passing remind_at=None cancels any AUTO row this task still has and writes
    nothing new, which is what retires the T-30 email without a migration: rows
    scheduled before this change are cancelled the next time their task is
    touched, and no new ones are created. `timezone_name` is kept in the
    signature so the call sites read the same as the calendar hook beside them
    and so restoring the old behaviour is a one-line change here.

    Call after every task save. Never raises: a reminder that fails to sync
    must not cost the founder the task they just typed, which is the same rule
    the calendar hook next door follows.
    """
    try:
        return service.sync_task_reminder(
            task.founder_id, task,
            remind_at=None,
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


# --- the confirmation, sent the moment a task is scheduled -------------------

def _due_phrase(due_date: date, due_time: time | None, tz: str) -> str:
    """"Thursday, 11 September at 07:50 PM" -- the moment, as the founder set it.

    A task with a date but no time is shown at CALENDAR_DEFAULT_TASK_HOUR, the
    same 9am the calendar event uses, so the email and the calendar entry never
    disagree about when the thing is.
    """
    local = datetime.combine(due_date, due_time or time(hour=settings.CALENDAR_DEFAULT_TASK_HOUR),
                             tzinfo=_zone(tz))
    return local.strftime("%A, %d %B at %I:%M %p")


def lead_phrase(minutes: int) -> str:
    """"15 minutes before" / "2 hours before" / "when it is due".

    Whole hours and whole days are said as hours and days: "1440 minutes
    before" is technically true and reads like a machine wrote it.
    """
    if minutes <= 0:
        return "when it is due"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "1 day before" if days == 1 else f"{days} days before"
    if minutes % 60 == 0:
        hours = minutes // 60
        return "1 hour before" if hours == 1 else f"{hours} hours before"
    return f"{minutes} minutes before"


def send_task_scheduled(to: str, name: str, title: str, when: str,
                        lead: str = "30 minutes before") -> bool:
    """Confirm one newly scheduled task. Returns False if it did not go out.

    No note field, unlike send_task_reminder: a note belongs to a Reminder, not
    to a Task, so there is never one to show here.
    """
    subject = f"Scheduled: {title}"
    text = (
        f"Hi {name},\n\n"
        f"\"{title}\" is on your plan for {when}.\n\n"
        f"Open Plan Your Day: {_PLAN_URL}\n\n"
        f"You will get a reminder {lead}, in the app and on your calendar.\n\n"
        "The GoXL Team\n\n"
        "--\n"
        "To stop these, turn off task emails in Profile > Notifications."
    )
    # escape(): the title is whatever the founder typed. An ampersand in a task
    # name should not break the markup of their own email.
    html = (
        f"<p>Hi {escape(name)},</p>"
        f"<p><strong>{escape(title)}</strong> is on your plan for {escape(when)}.</p>"
        f'<p><a href="{_PLAN_URL}">Open Plan Your Day</a></p>'
        f"<p>You will get a reminder {escape(lead)}, in the app and on your calendar.</p>"
        f"<p>The GoXL Team</p>"
        f'<p style="color:#6b7280;font-size:12px">To stop these, turn off task '
        f"emails in Profile &gt; Notifications.</p>"
    )
    return send_email(to, subject, text, html)


def notify_task_scheduled(db: Session, founder: Founder, task: Task, *,
                          timezone_name: str = "UTC"):
    """Decide whether this founder gets a confirmation, and return the sending.

    Returns a zero-argument callable for the caller to run in the background,
    or None when nothing should be sent. Returning the work instead of doing it
    keeps SMTP -- which can take seconds, and can hang -- out of the request
    that just saved the task, and keeps FastAPI out of this module.

    NOTHING IS SENT FOR A TASK WITH NO DUE DATE. There is no moment to confirm;
    a task with no date is a list item, not an appointment. That is the same
    line reminder_time_for draws, and it means ticking off a title-only to-do
    never lands in anyone's inbox.

    Pro only, checked live against `founder.plan_type` rather than at any
    earlier point: Feature.EMAIL_NOTIFICATIONS sits in the advisor bundle and
    is sold as Pro on the pricing page.
    """
    if task.due_date is None:
        return None
    if not founder.email:
        return None

    try:
        from app.core.container import container
        entitlements = container.entitlement_service(db)
        if not entitlements.has_feature(founder.plan_type, Feature.EMAIL_NOTIFICATIONS):
            return None
    except Exception as exc:
        # A plan lookup that fails must not cost the founder their task, and
        # must not send either: silence is the safe side of an unknown plan.
        logger.warning("task email: could not resolve plan, not sending",
                       extra={"founder_id": founder.founder_id}, exc_info=exc)
        return None

    if not _wants_task_reminders(founder):
        return None

    to = founder.email
    name = founder.full_name or "there"
    title = task.title
    when = _due_phrase(task.due_date, task.due_time, timezone_name)
    lead = lead_phrase(lead_minutes_for(task))

    def _send() -> None:
        # Captured as plain strings on purpose: this runs after the response,
        # by which point the request's database session is closed and neither
        # `founder` nor `task` can be safely touched.
        try:
            if not send_task_scheduled(to, name, title, when, lead):
                logger.warning("task email not delivered",
                               extra={"founder_id": founder.founder_id,
                                      "path": f"task={title!r}"})
        except Exception as exc:
            logger.warning("task email failed",
                           extra={"founder_id": founder.founder_id}, exc_info=exc)

    return _send


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

    due_at = reminder.remind_at + timedelta(minutes=lead_minutes_for(task))
    when = _when_phrase(reminder.remind_at, due_at,
                        getattr(founder, "timezone", None) or settings.DISCOVERY_TIMEZONE)
    send_task_reminder(founder.email, founder.full_name or "there",
                       task.title, when, reminder.note)
    counts["sent"] += 1
    service.mark_reminder_sent(reminder.reminder_id)
