"""The one way a notification gets created.

Everything that wants to tell a founder something calls `notify()`. Nothing
inserts into `notifications` directly, because four rules have to hold on every
write and scattering them is how a bell becomes noise:

  1. THE TYPE MUST BE SWITCHED ON. `notification_types.is_active` is the kill
     switch -- one UPDATE silences a type for everyone with no deploy. It is
     checked here so a switched-off type stops at the source rather than being
     written and filtered later.

  2. NO DUPLICATES. `dedup_key` is unique per founder. A sweep that runs every
     few hours re-evaluates the same conditions each time, so "your credits
     expire in 3 days" would otherwise arrive three times a day until they did.
     Passing a key makes the write idempotent: the second attempt is a no-op.

  3. THE FOUNDER'S PREFERENCE WINS. `notification_preferences.in_app_all` off
     means the bell stays quiet.

  4. IT MUST NEVER BREAK THE CALLER. Notifying is always a side effect of
     something more important -- a payment, a booking, a page load. A founder's
     booking must not fail because we could not write a bell row.

DEDUP KEYS ARE ALSO HOW A NOTIFICATION REPEATS ON PURPOSE. Put the thing that
should make it fire again into the key: `credits_expiring:2026-10-01` fires once
per expiry date, `task_due_today:2026-09-07` fires once per day, and
`report_ready:412` fires once per report, ever. There is no separate "repeat"
setting -- the key IS the policy, which means you can read the policy off the
call site instead of hunting for it.
"""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models import Founder
from app.models.schema import Notifications

#: The feed only shows in_app. `email` rows exist in the same table for
#: delivery, and the bell repository filters them out.
CHANNEL_IN_APP = "in_app"

#: Cached per process. The vocabulary changes when somebody edits the table,
#: which is rare, and re-reading it on every write would put a query in front of
#: every notification. Cleared by `reset_type_cache()`, which the sweep calls on
#: each run so a switch flipped in the database takes effect within the hour
#: rather than at the next deploy.
_active_types: set[str] | None = None


def reset_type_cache() -> None:
    global _active_types
    _active_types = None


def _is_active(db: Session, type_: str) -> bool:
    global _active_types
    if _active_types is None:
        try:
            rows = db.execute(
                text("SELECT type FROM notification_types WHERE is_active = true")
            ).scalars().all()
            _active_types = set(rows)
        except SQLAlchemyError:
            # Table missing (a target that has not migrated). Fail OPEN: the
            # foreign key still rejects a bad type, and a silent notification
            # blackout is a worse failure than a possible extra row.
            logger.warning("notification_types unreadable; allowing writes", exc_info=True)
            return True
    return type_ in _active_types


def _wants_in_app(founder: Founder | None) -> bool:
    prefs = (getattr(founder, "notification_preferences", None) or {})
    return bool(prefs.get("in_app_all", True))


def notify(
    db: Session,
    *,
    founder_id: int,
    type: str,
    title: str,
    body: str,
    action_url: str | None = None,
    dedup_key: str | None = None,
    metadata: dict | None = None,
    founder: Founder | None = None,
) -> Notifications | None:
    """Create one in-app notification. Returns it, or None if nothing was written.

    None is a normal outcome, not a failure: the type is switched off, the
    founder has the bell muted, this exact notification already exists, or the
    write failed and was swallowed. Callers should not branch on it.
    """
    try:
        if not _is_active(db, type):
            return None

        if founder is None:
            founder = db.get(Founder, founder_id)
        if founder is None:
            return None
        if not _wants_in_app(founder):
            return None

        if dedup_key:
            existing = db.execute(
                select(Notifications.notification_id).where(
                    Notifications.founder_id == founder_id,
                    Notifications.dedup_key == dedup_key,
                ).limit(1)
            ).first()
            if existing:
                return None

        row = Notifications(
            founder_id=founder_id,
            type=type,
            channel=CHANNEL_IN_APP,
            # The columns are 200 and unbounded; truncating the title here means
            # a long business name in a template can never raise on insert.
            title=title[:200],
            body=body,
            action_url=(action_url or None) and action_url[:500],
            dedup_key=dedup_key,
            metadata_=metadata or {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except SQLAlchemyError:
        # Includes the unique index firing when two requests race on the same
        # dedup_key -- which is the index doing its job, not an error worth
        # surfacing.
        logger.warning(
            "could not write notification",
            extra={"path": f"founder_id={founder_id} type={type}"},
            exc_info=True,
        )
        try:
            db.rollback()
        except SQLAlchemyError:
            pass
        return None
