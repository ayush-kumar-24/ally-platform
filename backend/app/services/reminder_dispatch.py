"""Deliver the reminders founders have already scheduled.

Everything around this existed and nothing sent anything: founders could
schedule a reminder on a task (planning_reminders, channel in_app|email), the
repository could find the due ones and mark them sent, and `send_email` could
send. The worker joining those three was the missing piece, so every reminder
ever scheduled sat at status='scheduled' forever. Reminder.__doc__ names this
worker's exact shape -- "query due_reminders, send, mark_reminder_sent".

Three rules decide whether a due EMAIL reminder actually goes out:

1. The founder's plan must include Feature.EMAIL_NOTIFICATIONS (Rs 999). This
   is a paid promise on the pricing page, so it is enforced here rather than
   assumed -- a reminder scheduled while on Pro must not keep mailing after a
   downgrade.
2. The founder's own notification_preferences.email_reminders must not be off.
   An entitlement says we MAY email; a preference says whether they WANT it,
   and the preference wins.
3. There has to be somewhere to send it.

A reminder blocked by any of those is still marked sent, not left pending. The
alternative is a queue that grows forever, re-examining the same rows every ten
minutes and mailing a founder the moment they upgrade -- reminders about tasks
whose date has long passed. `skipped` in the result says how many, so a plan
boundary is visible in the job output rather than looking like silence.

In-app reminders are deliberately untouched: they are not a paid feature and
have no delivery step, so this worker would only mark them sent without doing
anything.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models import Founder
from app.models.schema import Notifications
from app.planning.models import ReminderChannel
from app.plans.catalog import Feature
from app.plans.service import EntitlementService
from app.services.email import send_email

#: The `type` a delivered reminder is filed under in `notifications`. Must stay
#: one of the values that table's CHECK constraint permits.
_NOTIFICATION_TYPE = "follow_up"


def _wants_email_reminders(founder: Founder) -> bool:
    """Same default as discovery_notifications: on unless explicitly turned off.
    Reading it the other way would silently stop mailing every founder who has
    never opened their notification settings."""
    prefs = founder.notification_preferences or {}
    return bool(prefs.get("email_reminders", True))


def _body(task_title: str, note: str) -> tuple[str, str]:
    line = f"A reminder about your task: {task_title}"
    extra_text = f"\n\nYour note: {note}" if note else ""
    extra_html = f"<p>Your note: {note}</p>" if note else ""
    text = (f"Hi,\n\n{line}{extra_text}\n\n"
            f"Open Plan Your Day to mark it done.\n\nAlly")
    html = (f"<p>{line}</p>{extra_html}"
            f"<p>Open Plan Your Day to mark it done.</p><p>Ally</p>")
    return text, html


def send_due_task_reminders(db: Session, *, now: datetime | None = None,
                            planning_service=None,
                            entitlements: EntitlementService | None = None) -> dict:
    """Send every email reminder that is now due. Call from a scheduled job.

    Returns counts for observability. One founder's failure never stops the
    sweep -- a bad address or a closed SMTP connection must not strand every
    reminder queued behind it.
    """
    from app.core.container import container

    now = now or datetime.now(timezone.utc)
    planning = planning_service or container.planning_service(db)
    entitlements = entitlements or container.entitlement_service(db)

    result = {"sent": 0, "skipped_plan": 0, "skipped_pref": 0,
              "skipped_no_email": 0, "failed": 0, "in_app": 0}

    for reminder in planning.due_reminders(before=now):
        if reminder.channel is not ReminderChannel.EMAIL:
            result["in_app"] += 1
            continue
        try:
            founder = db.get(Founder, reminder.founder_id)
            if founder is None:
                # The reminder outlived its founder. Marking it sent is what
                # stops it being reconsidered on every sweep forever.
                planning.mark_reminder_sent(reminder.reminder_id)
                result["skipped_no_email"] += 1
                continue

            if not entitlements.has_feature(getattr(founder, "plan_type", None),
                                            Feature.EMAIL_NOTIFICATIONS):
                planning.mark_reminder_sent(reminder.reminder_id)
                result["skipped_plan"] += 1
                continue
            if not _wants_email_reminders(founder):
                planning.mark_reminder_sent(reminder.reminder_id)
                result["skipped_pref"] += 1
                continue
            if not founder.email:
                planning.mark_reminder_sent(reminder.reminder_id)
                result["skipped_no_email"] += 1
                continue

            task = planning.repository.get_task(reminder.task_id)
            title = task.title if task is not None else "your plan"
            text, html = _body(title, reminder.note)

            send_email(founder.email, f"Reminder: {title}", text, html)
            # Marked sent whatever send_email returned. It is best-effort by
            # contract (False in stub mode and on a delivery error), so keying
            # the queue on its result would re-send the same reminder on every
            # sweep for as long as mail stays misconfigured.
            planning.mark_reminder_sent(reminder.reminder_id)

            db.add(Notifications(
                founder_id=founder.founder_id, type=_NOTIFICATION_TYPE, channel="email",
                title=f"Reminder: {title}"[:200], body=text, sent_at=now,
                metadata_={"reminder_id": reminder.reminder_id, "task_id": reminder.task_id},
            ))
            result["sent"] += 1
        except Exception as exc:  # noqa: BLE001 -- one bad reminder must not stop the sweep
            logger.error("reminder dispatch failed for one reminder, continuing sweep",
                         extra={"reminder_id": reminder.reminder_id, "error": str(exc)})
            db.rollback()
            result["failed"] += 1

    db.commit()
    return result
