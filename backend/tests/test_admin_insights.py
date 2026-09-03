"""Admin Panel proposal Phase 2: "Live now / Today / 7 days" on the dashboard.

`active_today` already existed as a query -- `select count(*) from founders
where last_active_at >= :since` -- but since nothing ever wrote
`last_active_at`, it always ran successfully and always answered 0. That is
why the fix here is two-sided: `record_last_active` (tests in
test_last_active_tracking.py) is the write these metrics were always
missing, and `live_now` / `active_7d` are the two windows the proposal asked
for alongside the one that already existed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.admin.insights import LIVE_WINDOW, SqlAlchemyInsightsRepository

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class FakeDb:
    """Records every query issued so a test can assert on the SQL shape and
    the bound parameters, not just the final metric list."""

    def __init__(self, value=0, *, raise_on=None):
        self.value = value
        self.raise_on = raise_on or set()   # substrings of SQL that should raise
        self.calls: list[tuple[str, dict]] = []

    def execute(self, clause, params=None):
        sql = str(clause)
        self.calls.append((sql, params or {}))
        if any(marker in sql for marker in self.raise_on):
            raise RuntimeError("simulated: source table unavailable")
        return _Result(self.value)

    def rollback(self):
        pass


def _by_key(metrics, key):
    return next(m for m in metrics if m.key == key)


def test_live_now_reads_within_the_live_window():
    db = FakeDb(value=3)
    metrics = SqlAlchemyInsightsRepository(db).metrics(NOW)
    live = _by_key(metrics, "live_now")
    assert live.value == 3
    assert live.available is True

    sql, params = next(c for c in db.calls if "live_since" in c[1])
    assert params["live_since"] == NOW - LIVE_WINDOW


def test_active_7d_reads_within_seven_days():
    db = FakeDb(value=12)
    metrics = SqlAlchemyInsightsRepository(db).metrics(NOW)
    week = _by_key(metrics, "active_7d")
    assert week.value == 12

    sql, params = next(c for c in db.calls if "week_since" in c[1])
    assert params["week_since"] == NOW - timedelta(days=7)


def test_active_today_still_present_and_uses_start_of_day():
    db = FakeDb(value=5)
    metrics = SqlAlchemyInsightsRepository(db).metrics(NOW)
    today = _by_key(metrics, "active_today")
    assert today.value == 5

    sql, params = next(c for c in db.calls if c[1].get("since") is not None)
    assert params["since"] == NOW.replace(hour=0, minute=0, second=0, microsecond=0)


def test_live_now_and_active_7d_and_active_today_are_three_separate_windows():
    """The proposal's exact ask: Live now / Today / 7 days, not one number
    reused three ways."""
    db = FakeDb(value=1)
    metrics = SqlAlchemyInsightsRepository(db).metrics(NOW)
    keys = {m.key for m in metrics}
    assert {"live_now", "active_today", "active_7d"} <= keys

    live_call = next(c for c in db.calls if "live_since" in c[1])
    today_call = next(c for c in db.calls if c[1].get("since") is not None)
    week_call = next(c for c in db.calls if "week_since" in c[1])
    windows = {live_call[1]["live_since"], today_call[1]["since"], week_call[1]["week_since"]}
    assert len(windows) == 3, "all three windows must be genuinely different timestamps"


def test_a_missing_last_active_column_degrades_that_one_card_not_the_dashboard():
    """Same honesty contract every other card already has: unavailable, not a
    confident wrong zero -- and it must not take out total_users etc. with it."""
    db = FakeDb(raise_on={"live_since", "week_since", "last_active_at"})
    metrics = SqlAlchemyInsightsRepository(db).metrics(NOW)

    assert _by_key(metrics, "live_now").available is False
    assert _by_key(metrics, "active_7d").available is False
    assert _by_key(metrics, "total_users").available is True
