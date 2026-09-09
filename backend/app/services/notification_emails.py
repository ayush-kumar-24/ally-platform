"""Deliver bell notifications to a founder's inbox. Pro only.

WHAT THIS IS. Ally has eighteen notification types across two mechanisms --
thirteen standing conditions re-evaluated whenever the bell is opened, and five
fired at the moment something happens. All of them go through
`app.notifications.writer.notify()` and land in `notifications` as a row with
channel='in_app'. Until now that was the end of the journey: if the founder did
not open the app, they never learned anything. This module is the second leg.

WHY IT SWEEPS INSTEAD OF SENDING AT THE CALL SITE. `notify()` runs inside
request handling -- `generate_for_founder` re-evaluates all thirteen standing
rules on every single bell open. Putting SMTP behind that would mean a page load
blocking on a mail server, and a mail outage degrading the bell. So `notify()`
is left exactly as it was, and this reads the rows it wrote.

WHAT MARKS A ROW DONE. `notifications.sent_at`, which nothing else has ever
used. It is stamped for every row the worker examines -- sent, skipped for plan,
skipped for preference, or dropped as stale -- because a row left NULL is
re-examined on every run forever, and the first genuinely undeliverable one
would be retried every fifteen minutes until someone noticed.

WHAT IS DELIBERATELY NOT EMAILED:

  * anything the founder has already read or dismissed in the bell. They are in
    the app; they have seen it. An email about it is noise.
  * types with `notification_types.email_enabled = false` -- the per-type
    switch, flipped with one UPDATE and no deploy.
  * anything older than NOTIFICATION_EMAIL_MAX_AGE_HOURS, so recovering from an
    outage does not mean mailing out a week of history.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.models import Founder
from app.models.schema import Notifications
from app.plans.catalog import Feature
from app.services.email import send_email

_APP_URL = "https://app.goxlally.ai"


def _email_enabled_types(db: Session) -> set[str] | None:
    """Types whose email delivery is switched on. None means "could not tell".

    Fails CLOSED, unlike the `is_active` read in the writer next door, and the
    asymmetry is deliberate: that one is choosing whether to write a row a
    founder may never look at, this one is choosing whether to put mail in
    somebody's inbox. An unreadable switch table should not become a decision
    to email everyone about everything.
    """
    try:
        rows = db.execute(
            text("SELECT type FROM notification_types "
                 "WHERE is_active = true AND email_enabled = true")
        ).scalars().all()
        return set(rows)
    except SQLAlchemyError:
        logger.warning("notification_types unreadable; sending no notification email",
                       exc_info=True)
        return None


def _wants_email(founder: Founder) -> bool:
    prefs = founder.notification_preferences or {}
    return bool(prefs.get("email_notifications", True))


def send_notification_email(to: str, name: str, notification: Notifications) -> bool:
    """One email for one bell notification."""
    action = notification.action_url or "/app"
    link = action if action.startswith("http") else f"{_APP_URL}{action}"
    subject = notification.title

    text_body = (
        f"Hi {name},\n\n"
        f"{notification.title}\n\n"
        f"{notification.body}\n\n"
        f"Open Ally: {link}\n\n"
        "The GoXL Team\n\n"
        "--\n"
        "To stop these, turn off notification emails in Profile > Notifications."
    )
    html_body = (
        f"<p>Hi {escape(name)},</p>"
        f"<p><strong>{escape(notification.title)}</strong></p>"
        f"<p>{escape(notification.body)}</p>"
        f'<p><a href="{escape(link, quote=True)}">Open Ally</a></p>'
        f"<p>The GoXL Team</p>"
        f'<p style="color:#6b7280;font-size:12px">To stop these, turn off '
        f"notification emails in Profile &gt; Notifications.</p>"
    )
    return send_email(to, subject, text_body, html_body)


def _pending_rows(db: Session) -> list[Notifications]:
    """The queue: written, not yet emailed, and still unseen in the bell.

    Ordered by founder so the sweep groups without a second pass, and by
    creation time so a founder's oldest notification is the first to be mailed
    when the per-run cap bites.
    """
    return list(db.execute(
        select(Notifications)
        .where(
            Notifications.sent_at.is_(None),
            Notifications.channel == "in_app",
            # Already seen in the app. They know; an email is noise.
            Notifications.is_read.is_(False),
            Notifications.dismissed_at.is_(None),
        )
        .order_by(Notifications.founder_id, Notifications.created_at)
    ).scalars().all())


def send_pending_notification_emails(db: Session, *, now: datetime | None = None) -> dict:
    """Email every notification that has not been emailed yet. Pro founders only.

    HOW OFTEN THIS MUST RUN. Every 15 minutes, alongside the other job sweeps.
    A notification's value decays fast -- "a task is due today" mailed tomorrow
    is worse than not mailing it -- and the max-age drop below turns a job that
    has stopped into silence rather than a delayed flood.

    Returns counts for observability. `capped` being non-zero means at least one
    founder generated more notifications in one window than the per-run cap, and
    is worth looking at rather than tuning away.
    """
    from app.core.container import container

    now = now or datetime.now(timezone.utc)
    counts = {"sent": 0, "skipped_plan": 0, "skipped_pref": 0, "skipped_type": 0,
              "stale": 0, "orphaned": 0, "capped": 0, "failed": 0}

    allowed_types = _email_enabled_types(db)
    if allowed_types is None:
        return counts                       # fail closed; nothing is stamped

    cutoff = now - timedelta(hours=settings.NOTIFICATION_EMAIL_MAX_AGE_HOURS)
    entitlements = container.entitlement_service(db)

    pending = _pending_rows(db)

    by_founder: dict[int, list[Notifications]] = defaultdict(list)
    for row in pending:
        by_founder[row.founder_id].append(row)

    for founder_id, rows in by_founder.items():
        try:
            _deliver_for_founder(db, entitlements, founder_id, rows,
                                 allowed_types, cutoff, counts)
        except Exception as exc:
            # One founder's bad row must not cost every other founder their mail.
            counts["failed"] += len(rows)
            logger.error("notification email batch failed",
                         extra={"founder_id": founder_id}, exc_info=exc)
    db.commit()
    return counts


def _stamp(row: Notifications, now: datetime) -> None:
    row.sent_at = now


def _deliver_for_founder(db: Session, entitlements, founder_id: int,
                         rows: list[Notifications], allowed_types: set[str],
                         cutoff: datetime, counts: dict) -> None:
    now = datetime.now(timezone.utc)
    founder = db.get(Founder, founder_id)

    # Founder gone, or no address to send to. Close the rows out rather than
    # re-reading them on every run for the rest of time.
    if founder is None or not founder.email:
        counts["orphaned"] += len(rows)
        for row in rows:
            _stamp(row, now)
        return

    # Sold as Pro on the pricing page (Feature.EMAIL_NOTIFICATIONS is in the
    # advisor bundle). Checked here rather than when the row was written, so an
    # upgrade starts the emails and a downgrade stops them with no backfill.
    # A pure catalog lookup against the founder's tier -- no query.
    if not entitlements.has_feature(founder.plan_type, Feature.EMAIL_NOTIFICATIONS):
        counts["skipped_plan"] += len(rows)
        for row in rows:
            _stamp(row, now)
        return

    if not _wants_email(founder):
        counts["skipped_pref"] += len(rows)
        for row in rows:
            _stamp(row, now)
        return

    sent_this_run = 0
    for row in rows:
        if row.type not in allowed_types:
            counts["skipped_type"] += 1
            _stamp(row, now)
            continue

        created = row.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created is not None and created < cutoff:
            counts["stale"] += 1
            _stamp(row, now)
            continue

        # Left UNSTAMPED on purpose: the overflow goes out on the next run
        # rather than being silently dropped.
        if sent_this_run >= settings.NOTIFICATION_EMAIL_MAX_PER_RUN:
            counts["capped"] += 1
            continue

        send_notification_email(founder.email, founder.full_name or "there", row)
        sent_this_run += 1
        counts["sent"] += 1
        _stamp(row, now)
