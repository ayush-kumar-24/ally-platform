"""Write the standing-condition notifications for every founder.

    python -m app.jobs.notification_sweep

Run it every few hours. Three or four times a day is plenty: the conditions it
looks for -- credits expiring, a task overdue, an account deletion counting down
-- change on the scale of days, not minutes.

RUNNING IT MORE OFTEN IS HARMLESS. Every rule carries a dedup key, so a second
run inside the same day writes nothing. There is no "already sent" bookkeeping
to corrupt and no way to double-notify by running it twice.

RUNNING IT LESS OFTEN IS NOT VERY HARMFUL EITHER, which is the unusual part.
The same rules run whenever a founder opens their notifications, so anyone
actually using Ally gets a fresh bell regardless of this job. What the sweep
catches is the founder who is NOT opening Ally -- and that is exactly who needs
telling that their account deletes on Thursday.

IT NEEDS ADMIN DATABASE CONTEXT. Every table it reads is founder-scoped by row
level security, and this job has no founder identity of its own -- it works
across all of them by definition. Without `set_admin_rls_context` it would
faithfully sweep zero rows and report success.

EXIT CODES, because a scheduler only really reads these:

    0  ran to completion, including "nothing needed writing".
    1  the job itself failed -- database unreachable, an unexpected exception.
"""

from __future__ import annotations

import sys

from app.core.logger import logger


def main() -> int:
    # Imported inside main so importing this module never needs a database.
    from app.db.session import SessionLocal, set_admin_rls_context
    from app.notifications.generator import sweep

    db = SessionLocal()
    try:
        # Must come before the first read -- see the module docstring.
        db.begin()
        set_admin_rls_context(db)

        result = sweep(db)
        if result.get("failed"):
            logger.error("notification sweep could not run", extra={"path": str(result)})
            return 1

        logger.info(
            "notification sweep complete",
            extra={"path": f"founders={result['founders']} written={result['written']}"},
        )
        print(f"notification sweep: {result['founders']} founders, "
              f"{result['written']} notifications written")
        return 0
    except Exception as exc:
        logger.error("notification sweep failed", exc_info=exc)
        print(f"notification sweep failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
