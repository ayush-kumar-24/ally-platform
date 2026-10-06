"""Coupon domain DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class DiscountType:
    """Plain constants, same reasoning as WebhookOutcome: a route handler puts
    one straight into JSON without needing `.value`."""

    PERCENT = "percent"
    FIXED = "fixed"


class RedemptionStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASED = "released"


@dataclass(frozen=True)
class Coupon:
    coupon_id: int
    code: str
    description: str | None
    discount_type: str
    discount_value: int
    applies_to: list[str] | None
    max_redemptions: int | None
    max_per_founder: int
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    #: Set for a trial coupon: instead of discounting a one-time order, it
    #: starts an autopay subscription -- the discounted price is paid up front
    #: for `trial_days`, then the plan's full price recurs until cancelled.
    trial_days: int | None = None

    @property
    def is_trial(self) -> bool:
        return bool(self.trial_days)

    def discount_for(self, list_price_inr: int) -> int:
        """Whole rupees off `list_price_inr`, floored at a ₹1 charge.

        A fixed coupon worth more than the plan must not produce a free or
        negative order: Razorpay cannot create one, and a founder who pays ₹1
        for a ₹199 plan got the deal they were promised as nearly as the
        gateway allows. The percent branch cannot reach here -- the CHECK caps
        it at 99% -- but the clamp covers both rather than trusting that.
        """
        if self.discount_type == DiscountType.PERCENT:
            raw = list_price_inr * self.discount_value // 100
        else:
            raw = self.discount_value
        return max(0, min(raw, list_price_inr - 1))


@dataclass(frozen=True)
class CouponQuote:
    """What the founder is shown before they commit to paying."""

    code: str
    description: str | None
    list_amount_inr: int
    discount_inr: int
    payable_inr: int
    #: Set when this code starts an autopay trial: `payable_inr` is then what
    #: is paid today, and `list_amount_inr` recurs monthly after the trial.
    trial_days: int | None = None
