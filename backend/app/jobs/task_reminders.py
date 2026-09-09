"""Send any due Plan Your Day task reminders by email.

    python -m app.jobs.task_reminders

Run it every 15 minutes. Reminders are scheduled for a specific minute and this
only sends rows already past it, so a founder's nudge is late by however long
the gap between runs is -- fifteen minutes of lateness on a thirty-minute
warning is tolerable, an hour is not.

Rows that came due while this was not running are dropped rather than sent (see
TASK_REMINDER_MAX_AGE_MINUTES); they are reported as `stale` so an outage shows
up in the scheduler's logs instead of arriving in somebody's inbox as twenty
emails about yesterday.

EXIT CODES, because a scheduler only really reads these:

    0  ran to completion. Includes "nothing was due", the normal case.
    1  the job itself failed -- database unreachable, an unexpected exception.
    2  email is not configured (EMAIL_HOST unset), so nothing could have been
       delivered no matter what was due.

2 is deliberately neither 0 nor 1, for the reason set out at length in
app/jobs/discovery_reminders.py: reminder delivery in this codebase has already
been silently dead once -- for months, behind a green run -- and a job that
reports success while sending nothing is how that happens.
"""

from __future__ import annotations

import sys

from app.core.config import settings
from app.core.logger import logger


def main() -> int:
    # Imported inside main so `--help`-style introspection and import of this
    # module never require a database or a configured environment.
    from app.db.session import SessionLocal, set_admin_rls_context
    from app.services.task_reminders import send_due_reminders

    if not settings.email_enabled:
        logger.error(
            "task reminder job: email is not configured, nothing can be sent",
            extra={"path": "EMAIL_HOST is unset"},
        )
        return 2

    db = SessionLocal()
    try:
        # THIS JOB HAS NO FOUNDER AND WORKS ACROSS ALL OF THEM.
        #
        # `planning_reminders`, `planning_tasks` and `founders` are all
        # founder-scoped under row level security, whose policy is
        # `founder_id = get_founder_id() OR app.current_admin`. A scheduled job
        # has no founder identity to offer, so without this the sweep below
        # matches NOTHING: every run finds zero due reminders, logs sent=0,
        # exits 0, and nobody is ever reminded -- with a green run every quarter
        # hour saying all is well. Exactly the failure this feature already had.
        #
        # Invisible in development, which connects as a BYPASSRLS superuser.
        # Same fix, and the same reason, as the discovery reminder job.
        db.begin()
        set_admin_rls_context(db)

        result = send_due_reminders(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("task reminder job failed", exc_info=exc)
        return 1
    finally:
        db.close()

    logger.info(
        "task reminder job complete",
        extra={"path": (
            f"sent={result['sent']} stale={result['stale']} "
            f"skipped_plan={result['skipped_plan']} "
            f"skipped_pref={result['skipped_pref']} "
            f"orphaned={result['orphaned']} failed={result['failed']}"
        )},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
