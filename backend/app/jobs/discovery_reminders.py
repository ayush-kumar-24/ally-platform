"""Send any due 24h / 1h discovery-call reminders.

    python -m app.jobs.discovery_reminders

Run it every 15 minutes. The windows are "within 24 hours" and "within 1 hour",
and each call carries a `reminder_sent_24h` / `reminder_sent_1h` flag that is set
once -- so running it more often is harmless, and running it rarely means a
founder gets the 1h reminder late or not at all.

EXIT CODES, because a scheduler only really reads these:

    0  ran to completion. Includes "nothing was due", which is the normal case.
    1  the job itself failed -- database unreachable, an unexpected exception.
       Something is wrong and a human should look.
    2  email is not configured (EMAIL_HOST unset), so no reminder could have
       been delivered no matter what was due.

2 is deliberately not 0. The function underneath returns cheerful zero counts in
that state, and a scheduler seeing a green run every 15 minutes would report
perfect health while no founder had ever received a reminder. That is the failure
this file exists to make visible -- reminders had no caller at all until
2026-09-05, and nobody noticed for months.

It is also deliberately not 1. Missing configuration is a known, expected state
during rollout; it should be distinguishable from the database being down.
"""

from __future__ import annotations

import sys

from app.core.config import settings
from app.core.logger import logger


def main() -> int:
    # Imported inside main so `--help`-style introspection and import of this
    # module never require a database or a configured environment.
    from app.db.session import SessionLocal
    from app.services.discovery_notifications import send_due_reminders

    if not settings.email_enabled:
        logger.error(
            "discovery reminder job: email is not configured, nothing can be sent",
            extra={"path": "EMAIL_HOST is unset -- see docs/DEAD-SETTINGS-AND-CALL-DELIVERY.md"},
        )
        return 2

    db = SessionLocal()
    try:
        result = send_due_reminders(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("discovery reminder job failed", exc_info=exc)
        return 1
    finally:
        db.close()

    logger.info(
        "discovery reminder job complete",
        extra={"path": (
            f"24h={result.get('24h', 0)} "
            f"1h={result.get('1h', 0)} "
            f"skipped_opted_out={result.get('skipped_pref', 0)}"
        )},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
