"""The trial grant must land in a bucket that can actually expire.

The testing phase gives each founder a one-month allowance that lapses and does
not return. That behaviour depends on a detail with no other guard: settle()
expires ONLY the `monthly` bucket, so a grant written to `bonus` is permanent no
matter what expiry date is stamped on the row.

That failure is silent. The date looks set, the column looks right, and the
credits simply never go away. These tests make the bucket choice explicit so
moving the grant back to `bonus` -- which reads like a harmless tidy-up -- fails
here instead of in production a month later.
"""

from datetime import datetime, timedelta, timezone

from app.credits.expiry import CreditState, settle

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
PAST = NOW - timedelta(days=1)


def test_monthly_expires_when_its_date_passes():
    state, steps = settle(
        CreditState(monthly=1_431, bonus=0, expires_at=PAST), NOW)
    assert state.monthly == 0
    assert state.total == 0
    assert any(s.type == "expire" for s in steps)


def test_bonus_does_not_expire_even_with_a_date_set():
    """The reason the grant cannot live in `bonus`. Not a bug -- bonus exists for
    grants meant to outlive a period -- but it makes bonus the wrong home for a
    trial allowance."""
    state, steps = settle(
        CreditState(monthly=0, bonus=1_431, expires_at=PAST), NOW)
    assert state.bonus == 1_431, "bonus expired; the trial grant could live there after all"
    assert state.total == 1_431
    assert not steps, "settlement acted on a bucket it does not own"


def test_nothing_expires_before_the_date():
    future = NOW + timedelta(days=5)
    state, steps = settle(
        CreditState(monthly=1_431, bonus=0, expires_at=future), NOW)
    assert state.monthly == 1_431 and not steps


def test_expiry_without_a_renewal_date_does_not_come_back():
    """The whole contract: it lapses once and is gone. A renewal_date would
    re-grant it, which is what a paid tier does and a trial must not."""
    state, _ = settle(
        CreditState(monthly=1_431, bonus=0, expires_at=PAST, renewal_date=None), NOW)
    assert state.monthly == 0
    # Settling again much later must still leave it at zero.
    later, steps = settle(state, NOW + timedelta(days=400))
    assert later.total == 0 and not steps


def test_a_renewal_date_would_bring_it_back():
    """Guards the inverse: if renewal_date is ever set on a trial account by
    mistake, the allowance silently returns forever. Pinned so that stops being
    an invisible one-column difference."""
    state, _ = settle(
        CreditState(monthly=1_431, bonus=0, expires_at=PAST,
                    renewal_date=PAST, monthly_allowance=1_431), NOW)
    assert state.monthly == 1_431, "renewal no longer re-grants; trial semantics may have changed"


def test_the_catalog_grant_is_sized_for_one_expiring_period():
    """Free's grant is a single trial allowance, not a recurring one: it must be
    delivered via signup_credits with monthly_credits at zero, or it would renew
    every month regardless of the expiry above."""
    from app.plans.catalog import PLANS, PlanTier

    free = PLANS[PlanTier.FREE]
    assert free.signup_credits > 0
    assert free.monthly_credits == 0, "Free would renew monthly and never truly expire"


# --- what the UI is told ----------------------------------------------------


class TestTrialStatus:
    """`trial` on GET /plans/me. Computed server-side on purpose: days_remaining
    from a browser clock is wrong for anyone whose device time is off or who is
    not on UTC, and "your trial ends in 3 days" showing a day early reads as a
    billing bug."""

    @staticmethod
    def _status(delta=None):
        from app.api.v1.plans.router import _trial_status
        if delta is None:
            return _trial_status(None)
        return _trial_status(datetime.now(timezone.utc) + delta)

    def test_paid_tiers_have_no_trial_block(self):
        assert self._status(None) is None

    def test_mid_trial_is_not_warning_yet(self):
        s = self._status(timedelta(days=30))
        assert s["days_remaining"] == 30
        assert s["expiring_soon"] is False and s["has_expired"] is False

    def test_warning_window_opens_at_three_days(self):
        assert self._status(timedelta(days=3))["expiring_soon"] is True
        assert self._status(timedelta(days=4))["expiring_soon"] is False

    def test_part_of_a_day_left_still_counts_as_a_day(self):
        """Ceiling, not floor: with 12 hours left the founder can still use Ally,
        so telling them '0 days' while it works is wrong."""
        s = self._status(timedelta(hours=12))
        assert s["days_remaining"] == 1 and s["expiring_soon"] is True

    def test_expired_is_distinguishable_from_expiring(self):
        s = self._status(timedelta(days=-1))
        assert s["has_expired"] is True
        assert s["expiring_soon"] is False, "an ended trial is not 'ending soon'"
        assert s["days_remaining"] == 0


# --- the 402 a founder actually sees ----------------------------------------


def test_out_of_credits_says_spent_when_the_balance_ran_out():
    from app.plans.errors import OutOfCreditsError

    err = OutOfCreditsError(0, 1)
    assert err.status_code == 402
    assert "Not enough credits" in err.message
    assert err.expired_at is None


def test_out_of_credits_says_expired_when_the_trial_lapsed():
    """A founder whose trial ended with credits unused, told they are 'out of
    credits', will reasonably think something is broken."""
    from app.plans.errors import OutOfCreditsError

    when = datetime(2026, 9, 4, tzinfo=timezone.utc)
    err = OutOfCreditsError(0, 1, expired_at=when)
    assert err.status_code == 402
    assert "trial ended" in err.message and "4 September" in err.message
    assert "Not enough credits" not in err.message
    assert err.expired_at == when
