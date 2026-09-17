"""Reading and writing each founder's chosen lines.

ONE ROW PER FOUNDER, PER DAY, PER SURFACE. Rows are kept rather than
overwritten, which is what makes "do not repeat within a fortnight" answerable
at all -- a table that stored only today could not tell you what yesterday was.

`source` records whether the model chose the line or the deterministic fallback
did. It is the only way to notice that the provider has been quietly failing
for a week and every founder has been reading fallback picks: the cards look
completely normal either way, which is the point of the fallback and also the
risk of it.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.quotes.service import NO_REPEAT_DAYS, SURFACES


def picks_for(db: Session, founder_id: int, day: date) -> dict[str, str]:
    """`{surface: quote_id}` already stored for this founder-day, if any."""
    rows = db.execute(
        text(
            "select surface, quote_id from founder_daily_quotes "
            "where founder_id = :fid and quote_date = :day"
        ),
        {"fid": founder_id, "day": day},
    ).mappings().all()
    return {r["surface"]: r["quote_id"] for r in rows if r["surface"] in SURFACES}


def recent_ids(db: Session, founder_id: int, day: date,
               *, days: int = NO_REPEAT_DAYS) -> frozenset[str]:
    """Everything this founder has been shown in the last `days`."""
    rows = db.execute(
        text(
            "select distinct quote_id from founder_daily_quotes "
            "where founder_id = :fid and quote_date > :since and quote_date <= :day"
        ),
        {"fid": founder_id, "since": day - timedelta(days=days), "day": day},
    ).scalars().all()
    return frozenset(r for r in rows if r)


def store(db: Session, founder_id: int, day: date,
          picks: dict[str, str], source: str) -> None:
    """Write this founder-day's picks.

    Idempotent by primary key: a job that runs twice, or a read that races the
    nightly job, must not leave a founder with two different lines on one page
    or blow up on a duplicate. The first write wins -- re-picking mid-day would
    change the card under a founder who is looking at it.
    """
    for surface, quote_id in picks.items():
        if surface not in SURFACES:
            continue
        db.execute(
            text(
                "insert into founder_daily_quotes "
                "  (founder_id, quote_date, surface, quote_id, source) "
                "values (:fid, :day, :surface, :qid, :source) "
                "on conflict (founder_id, quote_date, surface) do nothing"
            ),
            {"fid": founder_id, "day": day, "surface": surface,
             "qid": quote_id, "source": source},
        )


def prune(db: Session, day: date, *, keep_days: int = 60) -> int:
    """Drop rows older than `keep_days`. Returns how many went.

    The table grows by two rows per founder per day forever otherwise, to serve
    a fourteen-day question. Sixty days leaves room to look back at what a
    founder was being shown when they complained about something.
    """
    result = db.execute(
        text("delete from founder_daily_quotes where quote_date < :cutoff"),
        {"cutoff": day - timedelta(days=keep_days)},
    )
    return result.rowcount or 0
