"""Discovery-call emails: booking confirmation + 24h/1h reminders.

Confirmation is transactional (always sent on booking). Reminders respect the
founder's notification_preferences.email_reminders flag and are meant to be
driven by a scheduled job calling `send_due_reminders` (e.g. every 15 min via
cron / APScheduler / a Supabase scheduled function). The scheduler itself is
deployment infra, not built here.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Founder
from app.models.schema import DiscoveryCalls
from app.services.email import send_email


def _fmt(dt: datetime, tz: str) -> str:
    return dt.astimezone(ZoneInfo(tz)).strftime("%A, %d %B %Y at %I:%M %p")


def send_booking_confirmation(to: str, name: str, scheduled_at: datetime, meeting_link: str,
                              tz: str | None = None, duration: int | None = None) -> bool:
    tz = tz or settings.DISCOVERY_TIMEZONE
    duration = duration or settings.DISCOVERY_CALL_DURATION_MINUTES
    when = _fmt(scheduled_at, tz)
    subject = "Your GoXL discovery call is confirmed"
    text = (
        f"Hi {name},\n\n"
        f"Your discovery call is confirmed for {when} ({tz}), {duration} minutes.\n\n"
        f"Join here: {meeting_link}\n\n"
        f"See you then,\nThe GoXL Team"
    )
    html = (
        f"<p>Hi {name},</p>"
        f"<p>Your discovery call is confirmed for <strong>{when}</strong> ({tz}), {duration} minutes.</p>"
        f'<p><a href="{meeting_link}">Join the call</a></p>'
        f"<p>See you then,<br>The GoXL Team</p>"
    )
    return send_email(to, subject, text, html)


def send_reminder(to: str, name: str, scheduled_at: datetime, meeting_link: str,
                  which: str, tz: str | None = None) -> bool:
    tz = tz or settings.DISCOVERY_TIMEZONE
    when = _fmt(scheduled_at, tz)
    label = "in 24 hours" if which == "24h" else "in 1 hour"
    subject = f"Reminder: your GoXL discovery call is {label}"
    text = (
        f"Hi {name},\n\n"
        f"A reminder that your discovery call is {label} - {when} ({tz}).\n\n"
        f"Join: {meeting_link}\n\nThe GoXL Team"
    )
    html = (
        f"<p>Hi {name},</p>"
        f"<p>A reminder that your discovery call is <strong>{label}</strong> - {when} ({tz}).</p>"
        f'<p><a href="{meeting_link}">Join the call</a></p><p>The GoXL Team</p>'
    )
    return send_email(to, subject, text, html)


def _wants_email_reminders(founder: Founder) -> bool:
    prefs = founder.notification_preferences or {}
    return bool(prefs.get("email_reminders", True))  # default on


def send_due_reminders(db: Session, *, now: datetime | None = None) -> dict:
    """Send any 24h / 1h reminders that are now due. Call from a scheduled job.

    A reminder is due when the call is within its window, still upcoming, not
    cancelled, its flag is not yet set, and the founder wants email reminders.
    Returns counts for observability.
    """
    now = now or datetime.now(timezone.utc)
    sent = {"24h": 0, "1h": 0, "skipped_pref": 0}

    windows = [
        ("24h", DiscoveryCalls.reminder_sent_24h, now + timedelta(hours=24)),
        ("1h", DiscoveryCalls.reminder_sent_1h, now + timedelta(hours=1)),
    ]
    for which, flag_col, horizon in windows:
        stmt = (
            select(DiscoveryCalls, Founder)
            .join(Founder, Founder.founder_id == DiscoveryCalls.founder_id)
            .where(
                flag_col.is_(False),
                DiscoveryCalls.status.in_(["pending", "confirmed"]),
                DiscoveryCalls.scheduled_at > now,
                DiscoveryCalls.scheduled_at <= horizon,
            )
        )
        for call, founder in db.execute(stmt).all():
            if not _wants_email_reminders(founder):
                sent["skipped_pref"] += 1
            elif founder.email:
                send_reminder(founder.email, founder.full_name, call.scheduled_at, call.meeting_link, which)
                sent[which] += 1
            setattr(call, "reminder_sent_24h" if which == "24h" else "reminder_sent_1h", True)
        db.commit()

    return sent
