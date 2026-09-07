"""CouponService -- decide whether a code applies, and what it is worth.

Every rejection raises a specific error rather than returning False, because
the founder needs to know WHICH thing went wrong: a typo and "you already used
this" have different next actions, and a code that is merely wrong for their
plan is still good for another one.

Validation runs twice per checkout, on purpose. `quote()` powers the live
preview when the founder types a code, and `reserve()` runs the same checks
again inside the transaction that creates the payment. The gap between the two
is exactly where the last slot of a capped code gets taken by somebody else, so
the second check is the one that decides.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
from app.coupons.models import Coupon, CouponQuote
from app.coupons.repository import CouponRepository
from app.plans.catalog import PLANS, PlanTier


def normalise(code: str) -> str:
    """Codes are compared upper-cased and trimmed. Founders type them off a
    slide, an email or a sticker; case and a trailing space are not a decision
    they were asked to make."""
    return (code or "").strip().upper()


class CouponService:
    def __init__(self, repository: CouponRepository, *, clock=None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- read-only preview --------------------------------------------------

    def quote(self, *, code: str, tier: PlanTier, founder_id: int) -> CouponQuote:
        """What this code is worth to this founder on this plan, or raise."""
        plan = PLANS.get(tier)
        if plan is None or not plan.is_paid:
            raise CouponNotApplicableError()

        coupon = self._validated(code=code, tier=tier, plan_name=plan.name,
                                 founder_id=founder_id)
        discount = coupon.discount_for(plan.price_inr)
        return CouponQuote(
            code=coupon.code,
            description=coupon.description,
            list_amount_inr=plan.price_inr,
            discount_inr=discount,
            payable_inr=plan.price_inr - discount,
        )

    # --- the binding check --------------------------------------------------

    def reserve(self, *, code: str, tier: PlanTier, founder_id: int,
                payment_id: int) -> tuple[Coupon, int]:
        """Re-validate and claim a slot against `payment_id`.

        Caller must be inside the transaction that created the payment row and
        must commit it: the reservation and the payment stand or fall together.
        """
        plan = PLANS[tier]
        coupon = self._validated(code=code, tier=tier, plan_name=plan.name,
                                 founder_id=founder_id)
        discount = coupon.discount_for(plan.price_inr)
        self.repository.reserve(coupon_id=coupon.coupon_id, founder_id=founder_id,
                                payment_id=payment_id, discount_inr=discount)
        return coupon, discount

    # --- shared rules -------------------------------------------------------

    def _validated(self, *, code: str, tier: PlanTier, plan_name: str,
                   founder_id: int) -> Coupon:
        coupon = self.repository.get_by_code(normalise(code))
        if coupon is None:
            raise CouponNotFoundError(normalise(code))

        if not coupon.is_active:
            raise CouponInactiveError()

        now = self._now()
        if coupon.valid_from > now:
            raise CouponNotYetValidError(coupon.valid_from)
        if coupon.valid_until <= now:
            raise CouponExpiredError(coupon.valid_until)

        if coupon.applies_to and tier.value not in coupon.applies_to:
            raise CouponNotValidForPlanError(plan_name)

        # Per-founder cap before the global one: "you already used this" is a
        # truer answer for that founder than "everyone has used it", and it is
        # the cheaper query.
        used_by_founder = self.repository.count_live_redemptions_by_founder(
            coupon.coupon_id, founder_id)
        if used_by_founder >= coupon.max_per_founder:
            raise CouponAlreadyUsedError()

        if coupon.max_redemptions is not None:
            if self.repository.count_live_redemptions(coupon.coupon_id) >= coupon.max_redemptions:
                raise CouponFullyRedeemedError()

        return coupon
