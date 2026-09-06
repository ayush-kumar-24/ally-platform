"""Founder-facing payments endpoints.

    POST /payments/checkout           start a Razorpay order for a paid plan
    POST /payments/coupons/validate   price a discount code before committing

This is the only payments endpoint a founder's own token can reach: nothing
here grants a plan. `POST /payments/checkout` only ever creates a *pending*
payment and hands back what the frontend needs to open Razorpay's Checkout.js
widget -- the plan itself is granted by the signed webhook
(app/api/v1/webhooks/razorpay.py), never from anything a founder's browser
can claim on its own.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.payments.models import CheckoutSession
from app.plans.catalog import PlanTier

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: PlanTier
    # A CODE, never an amount. The price is the catalog's to decide; see
    # PaymentService.start_checkout.
    coupon_code: str | None = Field(default=None, max_length=40)


class CouponValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: PlanTier
    code: str = Field(min_length=1, max_length=40)


class CouponQuoteResponse(BaseModel):
    """What the founder is shown before they pay. Rupees, not paise: this is
    display copy, and every other price on the billing page is in rupees."""

    code: str
    description: str | None
    list_amount_inr: int
    discount_inr: int
    payable_inr: int


class CheckoutResponse(BaseModel):
    payment_id: int
    order_id: str
    amount_paise: int
    currency: str
    key_id: str
    # Present only on a discounted order. `amount_paise` is always the amount
    # Razorpay will charge, so a client ignoring these still charges correctly.
    list_amount_paise: int | None = None
    discount_paise: int | None = None
    coupon_code: str | None = None

    @classmethod
    def from_domain(cls, s: CheckoutSession) -> "CheckoutResponse":
        return cls(payment_id=s.payment_id, order_id=s.order_id, amount_paise=s.amount_paise,
                   currency=s.currency, key_id=s.key_id,
                   list_amount_paise=s.list_amount_paise, discount_paise=s.discount_paise,
                   coupon_code=s.coupon_code)


def get_payment_service(db=Depends(get_db)):
    return container.payment_service(db)


def get_coupon_service(db=Depends(get_db)):
    return container.coupon_service(db)


@router.post("/coupons/validate", response_model=CouponQuoteResponse,
            summary="Price a discount code without committing to it")
def validate_coupon(
    payload: CouponValidateRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_coupon_service),
) -> CouponQuoteResponse:
    """Powers the live preview on the checkout page. Reserves nothing: a
    founder can price a code, think about it, and price it again. The claim
    happens at checkout, which re-runs every one of these checks -- so a code
    that quotes cleanly can still be gone by the time they press Pay, and that
    is the honest behaviour for a capped code."""
    quote = service.quote(code=payload.code, tier=payload.tier,
                          founder_id=founder.founder_id)
    return CouponQuoteResponse(
        code=quote.code, description=quote.description,
        list_amount_inr=quote.list_amount_inr, discount_inr=quote.discount_inr,
        payable_inr=quote.payable_inr)


@router.post("/checkout", response_model=CheckoutResponse,
            summary="Start a Razorpay order for a paid plan")
def start_checkout(
    payload: CheckoutRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
) -> CheckoutResponse:
    session = service.start_checkout(founder.founder_id, payload.tier,
                                     coupon_code=payload.coupon_code)
    return CheckoutResponse.from_domain(session)
