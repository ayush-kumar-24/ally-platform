"""Founder-facing payments endpoints.

    POST /payments/checkout           start a Razorpay order for a paid plan
    POST /payments/confirm            settle a just-paid order without waiting
                                      for the webhook
    POST /payments/coupons/validate   price a discount code before committing

`POST /payments/checkout` only ever creates a *pending* payment and hands back
what the frontend needs to open Razorpay's Checkout.js widget.

`POST /payments/confirm` is reachable with a founder's own token and can end in
a plan grant, which makes it worth being precise about: it grants nothing the
browser tells it. The request is a TRIGGER -- "Razorpay's handler just fired
for this order" -- and the service answers it by asking Razorpay directly
(callback signature under the key secret, then a server-to-server read of the
payment entity). What it buys is time: without it the founder watches an
"activating" spinner for as long as the webhook takes to arrive, which is
Razorpay's schedule and not ours. The signed webhook
(app/api/v1/webhooks/razorpay.py) remains the path that works when the founder
closes the tab, and both end in the same idempotent grant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db, set_admin_rls_context
from app.models import Founder
from app.payments.models import CheckoutSession, WebhookOutcome
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


class ConfirmRequest(BaseModel):
    """Exactly what Razorpay's Checkout.js handler hands the browser. No amount,
    no tier, no founder id: everything that decides the outcome is either
    already on the payment row or comes back from Razorpay itself."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1, max_length=64)
    razorpay_payment_id: str = Field(min_length=1, max_length=64)
    # Optional so a widget flow that does not surface it (or a founder
    # returning to a still-pending order later) can still be confirmed -- the
    # gateway fetch below is what actually settles capture either way.
    razorpay_signature: str | None = Field(default=None, max_length=128)


class ConfirmResponse(BaseModel):
    """`activated` is the only field the UI needs to branch on. `outcome` is
    the service's own word for what happened, kept for support and logs."""

    activated: bool
    outcome: str
    plan: str | None = None


@router.post("/confirm", response_model=ConfirmResponse,
            summary="Confirm a just-completed checkout with Razorpay")
def confirm_checkout(
    payload: ConfirmRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
    db=Depends(get_db),
) -> ConfirmResponse:
    """Same reason the webhook route sets it: granting a plan writes rows across
    `payments`, `subscriptions`, `founders` and `credit_transactions`, and the
    founder-isolation policies (migration d91c6e4b72aa) do not let a founder's
    own context write the subscription and plan rows that a *system* actor
    writes on their behalf. The elevation is narrow by construction -- the
    service has already refused any order that is not this founder's, and it
    grants only what Razorpay itself reports as captured. Transaction-local, so
    it dies with this request.
    """
    set_admin_rls_context(db)
    result = service.confirm_checkout(
        founder.founder_id, order_id=payload.order_id,
        gateway_payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )
    activated = result.outcome in (WebhookOutcome.CAPTURED, WebhookOutcome.ALREADY_PROCESSED)
    return ConfirmResponse(activated=activated, outcome=result.outcome, plan=result.plan)
