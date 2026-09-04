"""Coupons: authoring rules, validation, and the redemption ledger."""

from datetime import datetime, timedelta, timezone

import pytest

from app.admin.coupons import (
    CouponRejectedError,
    DiscountType,
    DuplicateCouponError,
    InvalidCouponError,
    build_coupon_service,
    describe_discount,
)

T0 = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


def service(now=T0):
    clock = now if callable(now) else (lambda: now)
    return build_coupon_service(clock=clock)


def make(s, code="BETA20", **kw):
    kw.setdefault("discount_type", DiscountType.PERCENT)
    kw.setdefault("discount_value", 20)
    return s.create(code=code, **kw)


# ── authoring ────────────────────────────────────────────────────────────────


def test_code_is_stored_upper_case():
    s = service()
    assert make(s, code="beta20").code == "BETA20"
    # ...and looked up case-insensitively, since founders retype it out of an email.
    assert s.get("beta20") is not None


@pytest.mark.parametrize("code", ["ab", "has space", "-LEADING", "emoji✨", ""])
def test_malformed_codes_are_rejected(code):
    with pytest.raises(InvalidCouponError):
        make(service(), code=code)


def test_duplicate_code_is_rejected():
    s = service()
    make(s)
    with pytest.raises(DuplicateCouponError):
        make(s)


def test_percentage_over_100_is_rejected():
    """A 120% discount would pay the founder to subscribe."""
    with pytest.raises(InvalidCouponError):
        make(service(), discount_type=DiscountType.PERCENT, discount_value=120)


def test_fixed_amount_may_exceed_100():
    """Fixed discounts are in paise, so 50000 is Rs 500 -- not a percentage."""
    c = make(service(), discount_type=DiscountType.FIXED, discount_value=50_000)
    assert describe_discount(c.discount_type, c.discount_value) == "Rs 500 off"


def test_expiry_must_follow_start():
    with pytest.raises(InvalidCouponError):
        make(service(), starts_at=T0, expires_at=T0 - timedelta(days=1))


def test_discount_value_is_not_editable():
    """A code somebody already redeemed at 20% must keep meaning 20%."""
    s = service()
    make(s)
    with pytest.raises(TypeError):
        s.update("BETA20", discount_value=50)


# ── validation ───────────────────────────────────────────────────────────────


def test_unknown_code_is_rejected_with_a_reason():
    result = service().validate("NOPE")
    assert result.valid is False
    assert "does not exist" in result.reason


def test_valid_code_carries_the_discount():
    s = service()
    make(s)
    result = s.validate("BETA20", founder_id=1)
    assert result.valid is True
    assert (result.discount_type, result.discount_value) == (DiscountType.PERCENT, 20)
    assert result.label == "20% off"


def test_deactivated_code_stops_validating():
    s = service()
    make(s)
    s.update("BETA20", active=False)
    assert s.validate("BETA20").valid is False


def test_code_is_not_valid_before_its_start():
    s = service()
    make(s, starts_at=T0 + timedelta(days=1))
    assert "not active yet" in s.validate("BETA20").reason


def test_expired_code_is_rejected():
    s = service()
    make(s, expires_at=T0 - timedelta(seconds=1))
    assert "expired" in s.validate("BETA20").reason


def test_plan_restriction_is_enforced():
    s = service()
    make(s, applies_to_plans=["pro"])
    assert s.validate("BETA20", plan="pro").valid is True
    assert s.validate("BETA20", plan="starter").valid is False


def test_plan_restricted_code_fails_closed_when_no_plan_is_named():
    """A caller that forgot to say what is being bought does not get a pass."""
    s = service()
    make(s, applies_to_plans=["pro"])
    result = s.validate("BETA20")
    assert result.valid is False
    assert "only applies to pro" in result.reason


def test_no_plan_restriction_means_every_plan():
    s = service()
    make(s)
    assert s.validate("BETA20", plan="starter").valid is True


# ── redemption ───────────────────────────────────────────────────────────────


def test_redeeming_writes_the_ledger_and_bumps_the_counter():
    s = service()
    make(s)
    s.redeem("BETA20", founder_id=7)
    items, total = s.list_redemptions("BETA20")
    assert total == 1
    assert items[0].founder_id == 7
    assert s.get("BETA20").redeemed_count == 1


def test_one_founder_cannot_use_a_single_use_code_twice():
    s = service()
    make(s)
    s.redeem("BETA20", founder_id=7)
    with pytest.raises(CouponRejectedError):
        s.redeem("BETA20", founder_id=7)
    # A different founder is unaffected.
    s.redeem("BETA20", founder_id=8)


def test_max_per_founder_above_one_is_honoured():
    s = service()
    make(s, max_per_founder=2)
    s.redeem("BETA20", founder_id=7)
    s.redeem("BETA20", founder_id=7)
    with pytest.raises(CouponRejectedError):
        s.redeem("BETA20", founder_id=7)


def test_global_cap_closes_the_code_for_everyone():
    s = service()
    make(s, max_redemptions=2)
    s.redeem("BETA20", founder_id=1)
    s.redeem("BETA20", founder_id=2)
    assert "fully claimed" in s.validate("BETA20", founder_id=3).reason
    with pytest.raises(CouponRejectedError):
        s.redeem("BETA20", founder_id=3)


def test_redeem_rechecks_rather_than_trusting_an_earlier_validate():
    """The gap between a UI's validate and its redeem is where a race lives."""
    s = service()
    make(s, max_redemptions=1)
    assert s.validate("BETA20", founder_id=2).valid is True   # looked fine...
    s.redeem("BETA20", founder_id=1)                          # ...someone else took it
    with pytest.raises(CouponRejectedError):
        s.redeem("BETA20", founder_id=2)


def test_expiry_is_checked_at_redemption_time_not_creation_time():
    now = {"t": T0}
    s = service(lambda: now["t"])
    make(s, expires_at=T0 + timedelta(days=1))
    s.redeem("BETA20", founder_id=1)
    now["t"] = T0 + timedelta(days=2)
    with pytest.raises(CouponRejectedError):
        s.redeem("BETA20", founder_id=2)


def test_credits_and_free_days_render_readably():
    assert describe_discount(DiscountType.CREDITS, 1500) == "1,500 bonus credits"
    assert describe_discount(DiscountType.FREE_DAYS, 30) == "30 days free"
    assert describe_discount(DiscountType.FIXED, 49_950) == "Rs 499.50 off"
