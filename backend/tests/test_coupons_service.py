"""CouponService -- the rules that decide what a founder pays.

Hand-written fakes, same approach as test_payments_service.py: these assert the
actual safety properties (a capped code cannot oversell, an expired one cannot
be revived, a founder cannot use the same code twice) without a database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.coupons.errors import (
    CouponAlreadyUsedError,
    CouponExpiredError,
    CouponFullyRedeemedError,
    CouponInactiveError,
    CouponNotApplicableError,
    CouponNotFoundError,
    CouponNotValidForPlanError,
    CouponNotYetValidError,
)
from app.coupons.models import Coupon, DiscountType
from app.coupons.service import CouponService, normalise
from app.plans.catalog import PLANS, PlanTier

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _coupon(**overrides) -> Coupon:
    base = dict(
        coupon_id=1, code="FOUNDER100", description="First 100 founders",
        discount_type=DiscountType.PERCENT, discount_value=50, applies_to=None,
        max_redemptions=100, max_per_founder=1,
        valid_from=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=30),
        is_active=True,
    )
    base.update(overrides)
    return Coupon(**base)


class FakeRepository:
    def __init__(self, coupon: Coupon | None = None, *, live=0, live_by_founder=0):
        self.coupon = coupon
        self.live = live
        self.live_by_founder = live_by_founder
        self.reserved: list[dict] = []

    def get_by_code(self, code):
        if self.coupon is not None and self.coupon.code == code:
            return self.coupon
        return None

    def count_live_redemptions(self, coupon_id):
        return self.live

    def count_live_redemptions_by_founder(self, coupon_id, founder_id):
        return self.live_by_founder

    def reserve(self, *, coupon_id, founder_id, payment_id, discount_inr):
        self.reserved.append({"coupon_id": coupon_id, "founder_id": founder_id,
                              "payment_id": payment_id, "discount_inr": discount_inr})
        return len(self.reserved)


def _service(repo: FakeRepository) -> CouponService:
    return CouponService(repo, clock=lambda: NOW)


# --- normalisation ----------------------------------------------------------

@pytest.mark.parametrize("typed", ["founder100", "  FOUNDER100  ", "Founder100"])
def test_codes_are_matched_case_and_space_insensitively(typed):
    """Founders type these off a slide or a sticker. Case and a stray space are
    not a decision anyone asked them to make."""
    repo = FakeRepository(_coupon())
    quote = _service(repo).quote(code=typed, tier=PlanTier.PRO, founder_id=1)
    assert quote.code == "FOUNDER100"


def test_normalise_handles_none():
    assert normalise(None) == ""


# --- pricing ----------------------------------------------------------------

def test_percentage_discount_comes_off_the_catalog_price():
    repo = FakeRepository(_coupon(discount_value=50))
    quote = _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)
    price = PLANS[PlanTier.PRO].price_inr

    assert quote.list_amount_inr == price
    assert quote.discount_inr == price // 2
    assert quote.payable_inr == price - price // 2


def test_fixed_discount_is_whole_rupees_off():
    repo = FakeRepository(_coupon(discount_type=DiscountType.FIXED, discount_value=100))
    quote = _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)
    assert quote.discount_inr == 100
    assert quote.payable_inr == PLANS[PlanTier.PRO].price_inr - 100


def test_a_fixed_discount_larger_than_the_plan_still_leaves_a_rupee_to_charge():
    """Razorpay cannot create an order for zero. A generous coupon must land on
    Rs 1, not on a checkout that dies at the gateway."""
    repo = FakeRepository(_coupon(discount_type=DiscountType.FIXED, discount_value=99_999))
    quote = _service(repo).quote(code="FOUNDER100", tier=PlanTier.BASIC, founder_id=1)
    assert quote.payable_inr == 1
    assert quote.discount_inr == PLANS[PlanTier.BASIC].price_inr - 1


def test_ninety_nine_percent_never_reaches_zero():
    repo = FakeRepository(_coupon(discount_value=99))
    for tier in (PlanTier.BASIC, PlanTier.STARTER, PlanTier.PRO):
        quote = _service(repo).quote(code="FOUNDER100", tier=tier, founder_id=1)
        assert quote.payable_inr >= 1


# --- rejection paths --------------------------------------------------------

def test_unknown_code_is_rejected_by_name():
    with pytest.raises(CouponNotFoundError):
        _service(FakeRepository(None)).quote(code="NOPE", tier=PlanTier.PRO, founder_id=1)


def test_deactivated_code_is_rejected():
    repo = FakeRepository(_coupon(is_active=False))
    with pytest.raises(CouponInactiveError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_expired_code_is_rejected():
    repo = FakeRepository(_coupon(valid_until=NOW - timedelta(seconds=1)))
    with pytest.raises(CouponExpiredError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_a_code_expiring_exactly_now_is_already_over():
    """The boundary is exclusive on purpose: "valid until 6pm" means 6pm is
    when it stops, not a second the founder can still squeeze into."""
    repo = FakeRepository(_coupon(valid_until=NOW))
    with pytest.raises(CouponExpiredError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_a_code_not_yet_started_is_rejected():
    repo = FakeRepository(_coupon(valid_from=NOW + timedelta(days=1)))
    with pytest.raises(CouponNotYetValidError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_a_code_scoped_to_other_plans_is_rejected():
    repo = FakeRepository(_coupon(applies_to=["basic"]))
    with pytest.raises(CouponNotValidForPlanError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_a_code_scoped_to_this_plan_is_accepted():
    repo = FakeRepository(_coupon(applies_to=["pro"]))
    assert _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_the_free_plan_takes_no_coupon():
    repo = FakeRepository(_coupon())
    with pytest.raises(CouponNotApplicableError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.FREE, founder_id=1)


# --- the caps ---------------------------------------------------------------

def test_the_hundredth_redemption_is_allowed_and_the_hundred_and_first_is_not():
    """The whole point of "first 100 customers": 100 gets in, 101 does not."""
    at_99 = FakeRepository(_coupon(max_redemptions=100), live=99)
    assert _service(at_99).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)

    at_100 = FakeRepository(_coupon(max_redemptions=100), live=100)
    with pytest.raises(CouponFullyRedeemedError):
        _service(at_100).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_an_uncapped_code_never_runs_out():
    repo = FakeRepository(_coupon(max_redemptions=None), live=10_000)
    assert _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_a_founder_cannot_use_the_same_code_twice():
    repo = FakeRepository(_coupon(), live_by_founder=1)
    with pytest.raises(CouponAlreadyUsedError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


def test_the_per_founder_message_wins_over_the_sold_out_one():
    """A founder who already used the code should be told that, not that
    everyone else took it -- they are different problems with different fixes."""
    repo = FakeRepository(_coupon(max_redemptions=100), live=100, live_by_founder=1)
    with pytest.raises(CouponAlreadyUsedError):
        _service(repo).quote(code="FOUNDER100", tier=PlanTier.PRO, founder_id=1)


# --- reserving --------------------------------------------------------------

def test_reserve_claims_a_slot_against_the_payment():
    repo = FakeRepository(_coupon())
    coupon, discount = _service(repo).reserve(
        code="founder100", tier=PlanTier.PRO, founder_id=42, payment_id=7)

    assert coupon.code == "FOUNDER100"
    assert discount == PLANS[PlanTier.PRO].price_inr // 2
    assert repo.reserved == [{"coupon_id": 1, "founder_id": 42, "payment_id": 7,
                              "discount_inr": discount}]


def test_reserve_re_runs_every_check_rather_than_trusting_the_quote():
    """The slot can be taken between the founder seeing a price and pressing
    Pay. reserve() is the check that actually decides."""
    repo = FakeRepository(_coupon(max_redemptions=100), live=100)
    with pytest.raises(CouponFullyRedeemedError):
        _service(repo).reserve(code="FOUNDER100", tier=PlanTier.PRO,
                               founder_id=1, payment_id=1)
    assert repo.reserved == []
