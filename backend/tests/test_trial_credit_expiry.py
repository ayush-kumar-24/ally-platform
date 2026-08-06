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
