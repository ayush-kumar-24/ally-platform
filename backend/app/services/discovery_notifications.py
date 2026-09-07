"""Discovery-call emails: booking confirmation + a single 1-hour reminder.

Confirmation is transactional (always sent on booking). The reminder respects
the founder's notification_preferences.email_reminders flag and is driven by a
scheduled job calling `send_due_reminders`, which must run AT LEAST HOURLY --
see that function for why a daily job silently sends nothing to most people.
The scheduler itself is deployment infra, not built here.

Two reminders (24h and 1h) were cut to one on 2026-09-07: two emails for one
30-minute call is how a founder learns to filter us.
"""

from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Founder
from app.models.schema import DiscoveryCalls
from app.services.email import send_email


def _fmt(dt: datetime, tz: str) -> str:
    return dt.astimezone(ZoneInfo(tz)).strftime("%A, %d %B %Y at %I:%M %p")


def _link_block(meeting_link: str | None) -> tuple[str, str]:
    """(html, text) for the join link -- or an honest stand-in if there is none.

    `meeting_link` can be None: the calendar call failed, or Workspace is not
    configured yet and GOXL_MEETING_URL is unset. That used to crash the whole
    email, so a founder who booked and paid got NO confirmation at all -- the
    worst possible outcome for the one email that has to arrive.
    """
    link = (meeting_link or settings.GOXL_MEETING_URL or "").strip()
    if link:
        safe = escape(link, quote=True)
        return (f'<p><a href="{safe}">Join the call</a></p>',
                f"Join here: {link}\n\n")
    return ("<p>We will email you the joining link before the call.</p>",
            "We will email you the joining link before the call.\n\n")


def send_booking_confirmation(to: str, name: str, scheduled_at: datetime, meeting_link: str,
                              tz: str | None = None, duration: int | None = None) -> bool:
    tz = tz or settings.DISCOVERY_TIMEZONE
    duration = duration or settings.DISCOVERY_CALL_DURATION_MINUTES
    when = _fmt(scheduled_at, tz)
    subject = "Your GoXL discovery call is confirmed"
    link_html, link_text = _link_block(meeting_link)
    text = (
        f"Hi {name},\n\n"
        f"Your discovery call is confirmed for {when} ({tz}), {duration} minutes.\n\n"
        + link_text +
        "Worth bringing: something specific -- your report, a decision you are "
        "stuck on, or a finding you disagree with. The call is far more useful "
        "with one real question than with a general catch-up.\n\n"
        "Need to move or cancel it? Open Discovery call in Ally, or reply to "
        "this email.\n\n"
        "See you then,\nThe GoXL Team"
    )
    # escape(): `name` is whatever the founder typed into their profile. An
    # ampersand or an angle bracket in it would break the markup of their own
    # email -- and this is the first email a paying founder ever gets from us.
    safe_name = escape(name)
    html = (
        f"<p>Hi {safe_name},</p>"
        f"<p>Your discovery call is confirmed for <strong>{escape(when)}</strong> "
        f"({escape(tz)}), {duration} minutes.</p>"
        + link_html +
        f"<p><strong>Worth bringing:</strong> something specific -- your report, a "
        f"decision you are stuck on, or a finding you disagree with. The call is "
        f"far more useful with one real question than with a general catch-up.</p>"
        f"<p>Need to move or cancel it? Open Discovery call in Ally, or reply to "
        f"this email.</p>"
        f"<p>See you then,<br>The GoXL Team</p>"
    )
    return send_email(to, subject, text, html)


def send_reminder(to: str, name: str, scheduled_at: datetime, meeting_link: str,
                  which: str = "1h", tz: str | None = None) -> bool:
    """`which` is kept so old callers and tests do not break; only "1h" is sent."""
    tz = tz or settings.DISCOVERY_TIMEZONE
    when = _fmt(scheduled_at, tz)
    label = "in 24 hours" if which == "24h" else "in 1 hour"
    subject = f"Reminder: your GoXL discovery call is {label}"
    link_html, link_text = _link_block(meeting_link)
    text = (
        f"Hi {name},\n\n"
        f"A reminder that your discovery call is {label} - {when} ({tz}).\n\n"
        + link_text + "The GoXL Team"
    )
    html = (
        f"<p>Hi {escape(name)},</p>"
        f"<p>A reminder that your discovery call is <strong>{escape(label)}</strong> "
        f"- {escape(when)} ({escape(tz)}).</p>"
        + link_html +
        "<p>The GoXL Team</p>"
    )
    return send_email(to, subject, text, html)


def _wants_email_reminders(founder: Founder) -> bool:
    prefs = founder.notification_preferences or {}
    return bool(prefs.get("email_reminders", True))  # default on


def send_due_reminders(db: Session, *, now: datetime | None = None) -> dict:
    """Send any 1h reminders that are now due. Call from a scheduled job.

    ONE REMINDER, NOT TWO. There was a 24h reminder as well; it was dropped on
    2026-09-07. Two emails for one 30-minute call is the amount of mail that
    teaches a founder to filter us, and the 24h one is the weaker of the pair --
    at that distance nobody changes their plans, they just note it and forget.
    The hour-before is the one that actually gets someone to the call.

    `reminder_sent_24h` is left in the table and simply never set. Dropping the
    column would rewrite history for calls that already had one, and it costs
    nothing to keep.

    HOW OFTEN THIS MUST RUN. Hourly, at least. The window below is "within the
    next hour", so a job that runs once a day would look once, find only the
    calls in the next 60 minutes, and miss every other call that day entirely --
    the reminder would simply never arrive for them. This is cheap to run: one
    indexed query, and it sends nothing at all unless a call is actually due.

    A reminder is due when the call is within the hour, still upcoming, not
    cancelled, its flag is not yet set, and the founder wants email reminders.
    Returns counts for observability.
    """
    now = now or datetime.now(timezone.utc)
    sent = {"1h": 0, "skipped_pref": 0}

    stmt = (
        select(DiscoveryCalls, Founder)
        .join(Founder, Founder.founder_id == DiscoveryCalls.founder_id)
        .where(
            DiscoveryCalls.reminder_sent_1h.is_(False),
            DiscoveryCalls.status.in_(["pending", "confirmed"]),
            DiscoveryCalls.scheduled_at > now,
            DiscoveryCalls.scheduled_at <= now + timedelta(hours=1),
        )
    )
    for call, founder in db.execute(stmt).all():
        if not _wants_email_reminders(founder):
            sent["skipped_pref"] += 1
        elif founder.email:
            send_reminder(founder.email, founder.full_name, call.scheduled_at,
                          call.meeting_link, "1h")
            sent["1h"] += 1
        # Flag set either way: a founder who opted out must not be re-checked
        # every hour for the rest of the day.
        call.reminder_sent_1h = True
    db.commit()

    return sent
