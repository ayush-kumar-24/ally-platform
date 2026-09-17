"""The midnight sweep that gives every founder their two lines for the day.

WHY A NIGHTLY JOB AND NOT A CALL ON PAGE LOAD. Two founders opening the Compass
fifty times a day would be a hundred model calls for a sentence that is not
allowed to change between them. Choosing once, at a moment nobody is looking,
costs one call per founder per day and makes the page itself free -- it reads a
row.

WHY IT IS ALSO SAFE TO RUN AT ANY OTHER TIME. Every write is `on conflict do
nothing`, and a founder who already has today's picks is skipped before any
model call is made. Running it twice costs nothing; running it late fills in
whoever is missing. That matters because the schedule is external (EventBridge)
and a missed firing should be recoverable by a manual one.

MIDNIGHT IS IST, the same boundary the token meter already resets on
(plans/usage.py). Two clocks in one product is how a founder ends up with a new
quote at 05:30 and a new token allowance at 00:00 and no way to explain either.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.plans.usage import usage_day
from app.quotes import repository
from app.quotes.service import build_context, fallback_pick, model_pick, shortlist
from app.services.llm.router import LLMTask
from app.services.llm.tasks import provider_for_task

#: Founders considered each night. A deleted or never-onboarded account does
#: not need a line chosen for a dashboard nobody will open.
_ACTIVE_FOUNDERS = text(
    "select founder_id from founders "
    "where deletion_executed_at is null "
    "order by founder_id"
)


def assign_daily_quotes(db: Session, *, now: datetime | None = None) -> dict:
    """Give every founder without today's picks their two lines.

    Returns a summary suitable for structured logging: how many founders were
    looked at, how many were already done, how many the model chose for, and
    how many fell back. That last number is the one worth watching -- fallback
    picks are invisible on the page, so a provider that has been failing all
    week looks exactly like one that is working.
    """
    moment = now or datetime.now(timezone.utc)
    day = usage_day(moment)

    founder_ids = list(db.execute(_ACTIVE_FOUNDERS).scalars().all())
    result = {"day": day.isoformat(), "founders": len(founder_ids),
              "already_done": 0, "by_model": 0, "by_fallback": 0, "pruned": 0}

    # Built once for the whole sweep rather than per founder: provider_for_task
    # reads the routing row and constructs a client, and doing that four dozen
    # times is four dozen pointless queries. A failure here is not fatal -- the
    # whole sweep falls back, which is a plainer page, not a broken one.
    provider = None
    if settings.DAILY_QUOTES_LLM:
        try:
            provider = provider_for_task(db, LLMTask.DAILY_QUOTE_SELECTION)
        except Exception as exc:  # no key, no routing row, unknown provider
            logger.warning("daily quotes: no provider, falling back for everyone",
                           extra={"error": str(exc)})

    for founder_id in founder_ids:
        try:
            if len(repository.picks_for(db, founder_id, day)) == 2:
                result["already_done"] += 1
                continue

            context = build_context(db, founder_id)
            candidates = shortlist(
                context, exclude=repository.recent_ids(db, founder_id, day)
            )

            picks = model_pick(provider, context, candidates) if provider else None
            source = "model"
            if not picks:
                picks = fallback_pick(context, candidates, day)
                source = "fallback"

            repository.store(db, founder_id, day, picks, source)
            db.commit()
            result["by_model" if source == "model" else "by_fallback"] += 1
        except Exception as exc:  # one bad profile must not end the sweep
            db.rollback()
            logger.warning("daily quotes: founder skipped",
                           extra={"founder_id": founder_id, "error": str(exc)})

    try:
        result["pruned"] = repository.prune(db, day)
        db.commit()
    except Exception as exc:  # housekeeping is never worth failing the job
        db.rollback()
        logger.warning("daily quotes: prune failed", extra={"error": str(exc)})

    logger.info("daily quote job complete", extra=result)
    return result


def ensure_today(db: Session, founder_id: int, *, now: datetime | None = None) -> dict[str, str]:
    """This founder's picks for today, choosing them now if the job has not.

    The read path's own safety net, for the founder who signed up at 11am and
    has no row from last midnight. Deliberately the DETERMINISTIC pick and not
    a model call: this runs inside a page load, where a model call would be
    latency the whole design exists to avoid, and tonight's sweep will not
    overwrite it (`store` is first-write-wins) so the line they see at 11am is
    the line they see all day.
    """
    moment = now or datetime.now(timezone.utc)
    day = usage_day(moment)

    picks = repository.picks_for(db, founder_id, day)
    if len(picks) == 2:
        return picks

    context = build_context(db, founder_id)
    candidates = shortlist(context, exclude=repository.recent_ids(db, founder_id, day))
    picks = fallback_pick(context, candidates, day)
    try:
        repository.store(db, founder_id, day, picks, "fallback")
        db.commit()
    except Exception as exc:  # serving the line matters more than storing it
        db.rollback()
        logger.warning("daily quotes: could not store on-read pick",
                       extra={"founder_id": founder_id, "error": str(exc)})
    return picks
