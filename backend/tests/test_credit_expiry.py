"""Credit lifecycle: expiry, renewal, spend order. Pure functions, no I/O."""

from datetime import datetime, timedelta, timezone

from app.credits.expiry import (
    CreditBucket,
    CreditState,
    add_month,
    settle,
    spend,
    start_period,
)

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def state(monthly=100, bonus=50, allowance=100, expires=None, renews=None):
    return CreditState(monthly=monthly, bonus=bonus, monthly_allowance=allowance,
                       expires_at=expires, renewal_date=renews)


# --- add_month --------------------------------------------------------------


def test_add_month_normal():
    assert add_month(datetime(2026, 1, 15)) == datetime(2026, 2, 15)


def test_add_month_year_rollover():
    assert add_month(datetime(2026, 12, 5)) == datetime(2027, 1, 5)


def test_add_month_clamps_short_months():
    """31 Jan + 1 month must not raise; it clamps to the last valid day."""
    assert add_month(datetime(2026, 1, 31)) == datetime(2026, 2, 28)
    assert add_month(datetime(2026, 3, 31)) == datetime(2026, 4, 30)


def test_add_month_leap_year():
    assert add_month(datetime(2028, 1, 31)) == datetime(2028, 2, 29)


# --- expiry -----------------------------------------------------------------


def test_nothing_due_is_a_no_op():
    s = state(expires=T0 + timedelta(days=5), renews=T0 + timedelta(days=5))
    settled, steps = settle(s, T0)
    assert settled == s and steps == []


def test_monthly_expires_bonus_survives():
    s = state(monthly=100, bonus=50, allowance=0, expires=T0 - timedelta(seconds=1))
    settled, steps = settle(s, T0)
    assert settled.monthly == 0 and settled.bonus == 50
    assert [x.type for x in steps] == ["expire"]
    assert steps[0].amount == -100 and steps[0].bucket is CreditBucket.MONTHLY


def test_expiry_records_before_and_after():
    s = state(monthly=100, bonus=50, allowance=0, expires=T0 - timedelta(seconds=1))
    _, steps = settle(s, T0)
    assert (steps[0].balance_before, steps[0].balance_after) == (150, 50)


def test_expiry_with_zero_monthly_is_skipped():
    s = state(monthly=0, bonus=50, allowance=0, expires=T0 - timedelta(days=1))
    _, steps = settle(s, T0)
    assert steps == []                       # nothing to expire -> no noise row


# --- renewal ----------------------------------------------------------------


def test_renewal_grants_allowance_and_moves_dates():
    s = state(monthly=0, bonus=50, allowance=200, renews=T0 - timedelta(seconds=1))
    settled, steps = settle(s, T0)
    assert settled.monthly == 200 and settled.bonus == 50
    assert [x.type for x in steps] == ["renew"]
    assert settled.renewal_date > T0 and settled.expires_at > T0


def test_expire_runs_before_renew_so_allowance_does_not_roll_over():
    """The whole point of expiry: an unused allowance must not accumulate."""
    past = T0 - timedelta(seconds=1)
    s = state(monthly=100, bonus=0, allowance=200, expires=past, renews=past)
    settled, steps = settle(s, T0)
    assert [x.type for x in steps] == ["expire", "renew"]
    assert settled.monthly == 200            # 200, not 300


def test_multiple_missed_periods_catch_up():
    """An account untouched for months lands on the current period, not one back."""
    s = state(monthly=0, bonus=0, allowance=100,
              renews=T0 - timedelta(days=95))
    settled, steps = settle(s, T0)
    assert settled.renewal_date > T0
    assert len([x for x in steps if x.type == "renew"]) >= 3
    assert settled.monthly == 100            # replaced each period, never summed


def test_settlement_is_idempotent():
    s = state(monthly=100, bonus=0, allowance=100, expires=T0 - timedelta(seconds=1),
              renews=T0 - timedelta(seconds=1))
    once, steps1 = settle(s, T0)
    twice, steps2 = settle(once, T0)
    assert twice == once and steps2 == []


# --- spend order ------------------------------------------------------------


def test_spend_uses_monthly_first():
    s = state(monthly=100, bonus=50)
    after, breakdown = spend(s, 30)
    assert (after.monthly, after.bonus) == (70, 50)
    assert breakdown == [(CreditBucket.MONTHLY, 30)]


def test_spend_spills_into_bonus():
    s = state(monthly=20, bonus=50)
    after, breakdown = spend(s, 35)
    assert (after.monthly, after.bonus) == (0, 35)
    assert breakdown == [(CreditBucket.MONTHLY, 20), (CreditBucket.BONUS, 15)]


def test_spend_exactly_empties_monthly():
    s = state(monthly=20, bonus=5)
    after, breakdown = spend(s, 20)
    assert (after.monthly, after.bonus) == (0, 5)
    assert breakdown == [(CreditBucket.MONTHLY, 20)]


def test_spend_from_bonus_only_when_monthly_empty():
    s = state(monthly=0, bonus=50)
    after, breakdown = spend(s, 10)
    assert after.bonus == 40 and breakdown == [(CreditBucket.BONUS, 10)]


# --- period start -----------------------------------------------------------


def test_start_period_sets_allowance_and_dates():
    s = start_period(CreditState(bonus=25), allowance=500, now=T0)
    assert s.monthly == 500 and s.bonus == 25 and s.monthly_allowance == 500
    assert s.expires_at == add_month(T0) and s.renewal_date == add_month(T0)


def test_total_is_sum_of_buckets():
    assert state(monthly=10, bonus=7).total == 17
