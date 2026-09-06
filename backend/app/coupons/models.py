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
