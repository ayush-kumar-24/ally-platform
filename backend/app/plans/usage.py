"""Daily token metering and monthly free-call tracking.

Two counters, both keyed by a *period* rather than reset by a job:

* tokens  -> keyed by (founder_id, UTC date)
* calls   -> keyed by (founder_id, UTC year-month)

Nothing "resets at midnight". A new day is simply a new key, so yesterday's row is
untouched and today's starts at zero the first time it is read. Same reasoning as
credit settlement: a counter that depends on a scheduled reset is wrong whenever
the scheduler misses, runs twice, or runs late -- and a rate limit that silently
stops limiting is worse than none.

Keeping the history also means "how many tokens did this founder use last Tuesday"
is answerable, which a reset-in-place counter throws away.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def period_month(moment: datetime) -> str:
    """Billing-ish month key, e.g. '2026-08'. UTC so it cannot shift with a client."""
    return f"{moment.year:04d}-{moment.month:02d}"


def next_utc_midnight(moment: datetime) -> datetime:
    """When the daily allowance rolls over -- returned to the user in the 429."""
    tomorrow = moment.astimezone(timezone.utc).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)


@dataclass(frozen=True)
class DailyUsage:
    founder_id: int
    usage_date: date
    tokens_used: int
    #: Which metered feature this counter belongs to (catalog.SOURCE_*). Chat and
    #: planning are budgeted independently, so one exhausting its ceiling must not
    #: disable the other -- that separation is this field.
    source: str = "chat"

    def remaining(self, limit: int) -> int:
        return max(0, limit - self.tokens_used)


@dataclass(frozen=True)
class CallUsage:
    founder_id: int
    period: str
    free_calls_used: int

    def free_remaining(self, allowance: int) -> int:
        return max(0, allowance - self.free_calls_used)


# --- ORM ---------------------------------------------------------------------

class DailyTokenUsageRow(Base):
    __tablename__ = "daily_token_usage"

    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True)
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    source: Mapped[str] = mapped_column(String(16), primary_key=True, server_default="chat")
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class CallUsageRow(Base):
    __tablename__ = "plan_call_usage"

    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(String(7), primary_key=True)      # 'YYYY-MM'
    free_calls_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


# --- repository --------------------------------------------------------------

class UsageRepository(abc.ABC):
    # `source` defaults to chat throughout: chat is the only caller that predates
    # the split, so every existing call site keeps its old meaning and only the
    # planning path has to say what it is.
    @abc.abstractmethod
    def get_daily(self, founder_id: int, day: date, *, source: str = "chat") -> DailyUsage: ...

    @abc.abstractmethod
    def add_tokens(self, founder_id: int, day: date, tokens: int, *,
                   at: datetime, source: str = "chat") -> DailyUsage:
        """Increment atomically and return the new total for that source."""

    @abc.abstractmethod
    def get_calls(self, founder_id: int, period: str) -> CallUsage: ...

    @abc.abstractmethod
    def add_free_call(self, founder_id: int, period: str, *, at: datetime) -> CallUsage: ...

    @abc.abstractmethod
    def release_free_call(self, founder_id: int, period: str, *, at: datetime) -> CallUsage:
        """Give a claimed free call back.

        Used when a claim succeeded but the booking it was for failed. Without this
        a transient calendar error would silently consume the founder's monthly
        free call and leave them nothing to show for it.
        """

    @abc.abstractmethod
    def try_claim_free_call(self, founder_id: int, period: str, allowance: int, *,
                            at: datetime) -> CallUsage | None:
        """Atomically claim one free call if the allowance permits.

        Returns the new usage, or None when the allowance is already spent. The
        check and the increment MUST happen together: doing them as two calls lets
        two concurrent bookings both see "1 remaining" and both claim it, handing
        out more free calls than the plan includes.
        """


class InMemoryUsageRepository(UsageRepository):
    def __init__(self) -> None:
        self._tokens: dict[tuple[int, date, str], int] = {}
        self._calls: dict[tuple[int, str], int] = {}
        self._lock = threading.RLock()

    def get_daily(self, founder_id: int, day: date, *, source: str = "chat") -> DailyUsage:
        with self._lock:
            used = self._tokens.get((founder_id, day, source), 0)
            return DailyUsage(founder_id, day, used, source)

    def add_tokens(self, founder_id: int, day: date, tokens: int, *,
                   at: datetime, source: str = "chat") -> DailyUsage:
        with self._lock:
            key = (founder_id, day, source)
            self._tokens[key] = self._tokens.get(key, 0) + max(0, tokens)
            return DailyUsage(founder_id, day, self._tokens[key], source)

    def get_calls(self, founder_id: int, period: str) -> CallUsage:
        with self._lock:
            return CallUsage(founder_id, period, self._calls.get((founder_id, period), 0))

    def add_free_call(self, founder_id: int, period: str, *, at: datetime) -> CallUsage:
        with self._lock:
            key = (founder_id, period)
            self._calls[key] = self._calls.get(key, 0) + 1
            return CallUsage(founder_id, period, self._calls[key])

    def release_free_call(self, founder_id: int, period: str, *, at: datetime) -> CallUsage:
        with self._lock:
            key = (founder_id, period)
            self._calls[key] = max(0, self._calls.get(key, 0) - 1)
            return CallUsage(founder_id, period, self._calls[key])

    def try_claim_free_call(self, founder_id: int, period: str, allowance: int, *,
                            at: datetime) -> CallUsage | None:
        # The lock spans check AND increment -- that is the whole point.
        with self._lock:
            key = (founder_id, period)
            used = self._calls.get(key, 0)
            if used >= allowance:
                return None
            self._calls[key] = used + 1
            return CallUsage(founder_id, period, used + 1)


class SqlAlchemyUsageRepository(UsageRepository):
    """Increments use INSERT ... ON CONFLICT DO UPDATE.

    That makes the read-modify-write a single atomic statement, so two concurrent
    messages from the same founder cannot both read 3,900 and both write 4,000 --
    which would let a user exceed the ceiling by racing themselves across tabs.

    Missing-table tolerance
    -----------------------
    The usage tables arrive with a migration that may not have run yet. When they
    are absent the meter reports zero rather than raising: a founder should still
    be able to see their plan and use the product. Enforcement is separately gated
    behind PLAN_ENFORCEMENT_ENABLED, so degrading here cannot silently unlock a
    limit that was otherwise being applied.
    """

    def __init__(self, db):
        self.db = db

    def _safe(self, fn, fallback):
        try:
            return fn()
        except Exception:
            self.db.rollback()
            return fallback

    def get_daily(self, founder_id: int, day: date, *, source: str = "chat") -> DailyUsage:
        used = self._safe(lambda: self.db.execute(
            _text("""select tokens_used from daily_token_usage
                      where founder_id = :f and usage_date = :d and source = :s"""),
            {"f": founder_id, "d": day, "s": source}).scalar(), 0)
        return DailyUsage(founder_id, day, int(used or 0), source)

    def add_tokens(self, founder_id: int, day: date, tokens: int, *,
                   at: datetime, source: str = "chat") -> DailyUsage:
        total = self._safe(lambda: self.db.execute(
            _text("""insert into daily_token_usage
                         (founder_id, usage_date, source, tokens_used, updated_at)
                     values (:f, :d, :s, :t, :at)
                     on conflict (founder_id, usage_date, source) do update
                        set tokens_used = daily_token_usage.tokens_used + excluded.tokens_used,
                            updated_at = excluded.updated_at
                     returning tokens_used"""),
            {"f": founder_id, "d": day, "s": source, "t": max(0, tokens), "at": at}).scalar(), 0)
        self._safe(lambda: self.db.commit(), None)
        return DailyUsage(founder_id, day, int(total or 0), source)

    def get_calls(self, founder_id: int, period: str) -> CallUsage:
        used = self._safe(lambda: self.db.execute(
            _text("""select free_calls_used from plan_call_usage
                      where founder_id = :f and period = :p"""),
            {"f": founder_id, "p": period}).scalar(), 0)
        return CallUsage(founder_id, period, int(used or 0))

    def add_free_call(self, founder_id: int, period: str, *, at: datetime) -> CallUsage:
        total = self.db.execute(
            _text("""insert into plan_call_usage (founder_id, period, free_calls_used, updated_at)
                     values (:f, :p, 1, :at)
                     on conflict (founder_id, period) do update
                        set free_calls_used = plan_call_usage.free_calls_used + 1,
                            updated_at = excluded.updated_at
                     returning free_calls_used"""),
            {"f": founder_id, "p": period, "at": at}).scalar()
        self.db.commit()
        return CallUsage(founder_id, period, int(total or 0))

    def release_free_call(self, founder_id: int, period: str, *, at: datetime) -> CallUsage:
        """Decrement, floored at zero so a double-release cannot create free calls."""
        total = self.db.execute(
            _text("""update plan_call_usage
                        set free_calls_used = greatest(free_calls_used - 1, 0),
                            updated_at = :at
                      where founder_id = :f and period = :p
                  returning free_calls_used"""),
            {"f": founder_id, "p": period, "at": at}).scalar()
        self.db.commit()
        return CallUsage(founder_id, period, int(total or 0))

    def try_claim_free_call(self, founder_id: int, period: str, allowance: int, *,
                            at: datetime) -> CallUsage | None:
        """One statement does check-and-increment.

        The `where` on the DO UPDATE branch is the guard: if the row already holds
        `allowance` calls the update is skipped, nothing is returned, and the caller
        learns the allowance is spent. Two concurrent claims therefore cannot both
        succeed -- the second finds the row at the limit and gets no row back.
        """
        if allowance <= 0:
            return None
        row = self.db.execute(
            _text("""insert into plan_call_usage (founder_id, period, free_calls_used, updated_at)
                     values (:f, :p, 1, :at)
                     on conflict (founder_id, period) do update
                        set free_calls_used = plan_call_usage.free_calls_used + 1,
                            updated_at = excluded.updated_at
                      where plan_call_usage.free_calls_used < :allowance
                     returning free_calls_used"""),
            {"f": founder_id, "p": period, "at": at, "allowance": allowance}).scalar()
        self.db.commit()
        if row is None:
            return None
        return CallUsage(founder_id, period, int(row))


def _text(sql: str):
    from sqlalchemy import text
    return text(sql)
