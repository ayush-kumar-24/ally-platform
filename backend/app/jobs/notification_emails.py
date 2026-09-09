"""Email any bell notifications that have not been emailed yet. Pro founders only.

    python -m app.jobs.notification_emails

Run it every 15 minutes, alongside the other sweeps. A notification's value
decays fast -- "a task is due today", mailed tomorrow, is worse than not mailed
at all -- and anything older than NOTIFICATION_EMAIL_MAX_AGE_HOURS is dropped
rather than sent, so a job that has been down produces silence instead of a
flood on recovery.

EXIT CODES, because a scheduler only really reads these:

    0  ran to completion. Includes "nothing was pending", the normal case.
    1  the job itself failed -- database unreachable, an unexpected exception.
    2  email is not configured (EMAIL_HOST unset), so nothing could have been
       delivered no matter what was pending.

2 is deliberately neither 0 nor 1, for the reason set out at length in
app/jobs/discovery_reminders.py: mail delivery in this codebase has already been
silently dead once, for months, behind a green run.
"""

from __future__ import annotations

import sys

from app.core.config import settings
from app.core.logger import logger


def main() -> int:
    # Imported inside main so `--help`-style introspection and import of this
    # module never require a database or a configured environment.
    from app.db.session import SessionLocal, set_admin_rls_context
    from app.services.notification_emails import send_pending_notification_emails

    if not settings.email_enabled:
        logger.error(
            "notification email job: email is not configured, nothing can be sent",
            extra={"path": "EMAIL_HOST is unset"},
        )
        return 2

    db = SessionLocal()
    try:
        # THIS JOB HAS NO FOUNDER AND WORKS ACROSS ALL OF THEM.
        #
        # `notifications` and `founders` are both founder-scoped under row level
        # security, whose policy is `founder_id = get_founder_id() OR
        # app.current_admin`. A scheduled job has no founder identity to offer,
        # so without this the sweep matches NOTHING: every run finds zero
        # pending rows, logs sent=0, exits 0, and nobody is ever emailed -- with
        # a green run every quarter hour saying all is well.
        #
        # Invisible in development, which connects as a BYPASSRLS superuser.
        # Same fix, and the same reason, as the notification sweep next door.
        db.begin()
        set_admin_rls_context(db)

        result = send_pending_notification_emails(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("notification email job failed", exc_info=exc)
        return 1
    finally:
        db.close()

    logger.info(
        "notification email job complete",
        extra={"path": (
            f"sent={result['sent']} stale={result['stale']} capped={result['capped']} "
            f"skipped_plan={result['skipped_plan']} skipped_pref={result['skipped_pref']} "
            f"skipped_type={result['skipped_type']} orphaned={result['orphaned']} "
            f"failed={result['failed']}"
        )},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
