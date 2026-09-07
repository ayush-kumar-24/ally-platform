"""Run the rules and write whatever is missing.

TWO CALLERS, ON PURPOSE.

  The SWEEP (`app/jobs/notification_sweep.py`) walks every founder on a timer.
  It is what catches the founder who has not opened Ally for a week and whose
  account deletes on Thursday.

  THE BELL ITSELF calls `generate_for_founder` when a founder opens their
  notifications. That is what makes the feed feel alive: whatever is true at the
  moment they look is there, rather than whatever was true when a cron last ran.

Both are safe to run as often as you like, because every rule carries a dedup
key and the second run writes nothing. That is the whole design -- there is no
"has this been sent" bookkeeping to get wrong, and no window where a founder
opening the app between sweeps sees a stale bell.

THE BELL PATH IS THROTTLED ANYWAY. Not for correctness -- for cost. A founder
refreshing the page ten times in a minute would otherwise run eleven table
reads each time to conclude nothing changed. Throttled in-process, because this
is a performance guard and not something worth a shared store: the worst case
when a server restarts is one extra sweep for one founder.
"""

from __future__ import annotations

import time
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models import Founder
from app.notifications import rules as rules_module
from app.notifications.writer import notify, reset_type_cache

#: How long before a founder's rules are re-run on the bell path.
_THROTTLE_S = 300.0
_last_run: dict[int, float] = defaultdict(float)


def generate_for_founder(
    db: Session, founder_id: int, *, founder: Founder | None = None,
    throttle: bool = False,
) -> int:
    """Evaluate every rule for one founder. Returns how many were written.

    Never raises. A rule that fails takes only itself down -- a missing table on
    one target must not silence the other ten rules.
    """
    if throttle:
        now = time.monotonic()
        if now - _last_run[founder_id] < _THROTTLE_S:
            return 0
        _last_run[founder_id] = now

    written = 0
    for rule in rules_module.ALL_RULES:
        try:
            for candidate in rule(db, founder_id):
                row = notify(
                    db,
                    founder_id=founder_id,
                    type=candidate.type,
                    title=candidate.title,
                    body=candidate.body,
                    action_url=candidate.action_url,
                    dedup_key=candidate.dedup_key,
                    founder=founder,
                )
                if row is not None:
                    written += 1
        except SQLAlchemyError:
            # Almost always a table this target has not migrated yet. Roll back
            # so the failed statement cannot poison the rules that follow.
            logger.warning("notification rule failed: %s", rule.__name__, exc_info=True)
            try:
                db.rollback()
            except SQLAlchemyError:
                pass
        except Exception:
            logger.warning("notification rule errored: %s", rule.__name__, exc_info=True)
    return written


def sweep(db: Session, *, limit: int | None = None) -> dict:
    """Run the rules for every founder who could plausibly need something.

    NOT every founder in the table. Deleted and suspended accounts are skipped,
    and so is anyone who has never signed in -- writing a bell notification for
    someone who has not arrived yet is work nobody will ever see.

    The type cache is cleared first, so a type switched off in the database
    takes effect on the next sweep rather than at the next deploy.
    """
    reset_type_cache()

    sql = """
        select founder_id
          from founders
         where coalesce(status, 'active') not in ('deleted', 'suspended', 'banned')
           and deletion_executed_at is null
           and last_active_at is not null
         order by last_active_at desc
    """
    if limit:
        sql += " limit :limit"

    try:
        ids = db.execute(text(sql), {"limit": limit} if limit else {}).scalars().all()
    except SQLAlchemyError:
        # `last_active_at` / `status` are admin-panel columns that one deployed
        # database may not have. Fall back to the columns that certainly exist
        # rather than sweeping nobody.
        logger.warning("founder sweep query failed; falling back", exc_info=True)
        try:
            db.rollback()
            ids = db.execute(text(
                "select founder_id from founders where deletion_executed_at is null"
            )).scalars().all()
        except SQLAlchemyError:
            logger.error("notification sweep could not list founders", exc_info=True)
            return {"founders": 0, "written": 0, "failed": True}

    written = 0
    for fid in ids:
        written += generate_for_founder(db, fid)
    return {"founders": len(ids), "written": written, "failed": False}
