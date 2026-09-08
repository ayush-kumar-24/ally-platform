"""The founder's own billing surface -- subscription, invoices, history and
the details an invoice has to carry.

    POST /payments/subscription          start a Plus/Pro recurring mandate
    GET  /payments/subscription          current subscription + entitlement
    POST /payments/subscription/cancel   cancel (at period end by default)
    GET  /payments/invoices              receipts, newest first
    GET  /payments/history               every payment, succeeded or not
    GET  /payments/billing-profile       name / GSTIN / address
    PUT  /payments/billing-profile       save them

Kept apart from router.py, which owns the one-time checkout, for the reason
panel_router_v2.py was split from panel_router.py: both mount under the same
prefix, and one module per concern stays readable. Everything here is
authenticated as a founder and scoped to their own rows -- `founder.founder_id`
comes from the token and is never read from the request body.

WHY THE PATHS SAY /payments AND NOT /billing. The implementation guide names
`/api/billing/*`. This codebase already serves `/payments/checkout`,
`/payments/confirm` and `/payments/coupons/validate`, and the frontend already
calls them. Two prefixes for one concern is worse than the guide's naming
being approximate, so the existing one wins and the mapping is noted here.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db, set_admin_rls_context
from app.models import Founder
from app.payments.subscription_repository import SubscriptionRecord
from app.plans.catalog import PLANS, PlanTier

router = APIRouter(prefix="/payments", tags=["payments"])


def get_subscription_service(db=Depends(get_db)):
    return container.subscription_service(db)


def get_billing_profile_service(db=Depends(get_db)):
    return container.billing_profile_service(db)


def get_subscription_repository(db=Depends(get_db)):
    from app.payments.subscription_repository import SubscriptionRepository
    return SubscriptionRepository(db)


# --- schemas ----------------------------------------------------------------

class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: A tier, never a price and never a Razorpay plan id. The plan id is
    #: looked up server-side from `razorpay_plans`; letting the browser name
    #: one would let a founder subscribe to whatever amount they liked.
    tier: PlanTier


class SubscribeResponse(BaseModel):
    """What the browser hands to Razorpay Checkout in subscription mode.

    `amount_inr` is display copy. The amount actually charged is fixed on the
    Razorpay Plan and cannot be influenced from here -- which is why, unlike
    the one-time order response, there is no `amount_paise` for the widget to
    quote back.
    """

    subscription_id: int
    razorpay_subscription_id: str
    key_id: str
    tier: str
    plan_name: str
    amount_inr: int
    currency: str
    short_url: str | None = None


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Default True and it should stay that way: the founder paid for this
    #: month. `False` is offered because a founder who says "stop it now"
    #: should be able to have that, not because it is the sensible default.
    at_period_end: bool = True
    reason: str | None = Field(default=None, max_length=500)


class CancelResponse(BaseModel):
    status: str
    cancel_at_period_end: bool
    access_until: datetime | None
    message: str


class SubscriptionResponse(BaseModel):
    """The billing page's whole top half.

    `entitlement` is what access actually depends on and is deliberately
    reported alongside the subscription rather than derived from its status by
    the client: a cancelled subscription can still be entitled (they paid for
    the rest of the month), and a client computing that itself would get it
    wrong in exactly the case that costs the most trust.
    """

    has_subscription: bool
    tier: str | None = None
    plan_name: str | None = None
    status: str | None = None
    amount_inr: int | None = None
    billing_cycle: str | None = None
    is_recurring: bool = False
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    next_charge_at: datetime | None = None
    cancel_at_period_end: bool = False
    cancelled_at: datetime | None = None
    started_at: datetime | None = None
    paid_count: int = 0
    entitlement: dict


class InvoiceResponse(BaseModel):
    invoice_id: int
    invoice_number: str | None
    gateway_invoice_id: str
    amount_inr: float
    tax_amount_inr: float | None
    total_amount_inr: float
    currency: str
    status: str
    #: Razorpay's own hosted document. We index invoices, we do not render
    #: them -- see app/payments/subscriptions.py.
    invoice_url: str | None
    issued_at: datetime | None
    paid_at: datetime | None


class PaymentHistoryResponse(BaseModel):
    payment_id: int
    amount_inr: float
    currency: str
    status: str
    plan_tier: str | None
    plan_name: str | None
    failure_reason: str | None
    paid_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime | None


class BillingProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_type: str = Field(pattern="^(individual|business)$")
    business_name: str | None = Field(default=None, max_length=200)
    gstin: str | None = Field(default=None, max_length=20)
    billing_address: str | None = Field(default=None, max_length=1000)
    billing_city: str | None = Field(default=None, max_length=100)
    billing_state: str | None = Field(default=None, max_length=100)
    billing_pincode: str | None = Field(default=None, max_length=10)
    billing_country: str = Field(default="IN", max_length=2)


class BillingProfileResponse(BaseModel):
    customer_type: str
    business_name: str | None
    gstin: str | None
    billing_address: str | None
    billing_city: str | None
    billing_state: str | None
    billing_pincode: str | None
    billing_country: str
    #: True when there is enough here to put on a GST invoice. The billing
    #: page prompts on this BEFORE checkout: details corrected after an
    #: invoice is issued do not change the invoice.
    is_invoice_ready: bool


# --- subscription -----------------------------------------------------------

@router.post("/subscription", response_model=SubscribeResponse,
             summary="Start a monthly subscription for Plus or Pro")
def start_subscription(
    payload: SubscribeRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_subscription_service),
) -> SubscribeResponse:
    """Creates the mandate; grants nothing.

    The founder is not charged by this call and does not have a plan when it
    returns. Razorpay charges the mandate once they authorise it in Checkout,
    and `subscription.charged` -- signed, server-to-server -- is what actually
    moves them onto the plan. That ordering is the whole design: see the
    module docstring of app/payments/subscriptions.py.
    """
    session = service.start_subscription(founder.founder_id, payload.tier)
    return SubscribeResponse(
        subscription_id=session.subscription_id,
        razorpay_subscription_id=session.gateway_subscription_id,
        key_id=session.key_id, tier=session.tier, plan_name=session.plan_name,
        amount_inr=session.amount_inr, currency=session.currency,
        short_url=session.short_url)


@router.get("/subscription", response_model=SubscriptionResponse,
            summary="My current subscription and entitlement")
def my_subscription(
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_subscription_service),
) -> SubscriptionResponse:
    record = service.current(founder.founder_id)
    entitlement = _entitlement(founder, record)
    if record is None:
        return SubscriptionResponse(has_subscription=False, entitlement=entitlement)

    plan = _plan_for(record.plan_type)
    return SubscriptionResponse(
        has_subscription=True, tier=record.plan_type,
        plan_name=plan.name if plan else record.plan_type,
        status=record.status, amount_inr=record.amount_inr,
        billing_cycle=record.billing_cycle, is_recurring=record.is_recurring,
        current_period_start=record.current_period_start,
        current_period_end=record.current_period_end,
        next_charge_at=record.next_charge_at,
        cancel_at_period_end=record.cancel_at_period_end,
        cancelled_at=record.cancelled_at, started_at=record.started_at,
        paid_count=record.paid_count, entitlement=entitlement)


@router.post("/subscription/cancel", response_model=CancelResponse,
             summary="Cancel my subscription")
def cancel_subscription(
    payload: CancelRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_subscription_service),
    db: Session = Depends(get_db),
) -> CancelResponse:
    """Same RLS elevation `POST /payments/confirm` takes, for the same reason:
    a cancellation writes the `subscriptions` row that a *system* actor owns,
    and the founder-isolation policies do not let a founder's own context
    write it on their behalf. Narrow by construction -- the service has already
    refused any subscription that is not this founder's."""
    set_admin_rls_context(db)
    result = service.cancel(founder.founder_id, at_period_end=payload.at_period_end,
                            reason=payload.reason)
    if result.access_until and result.cancel_at_period_end:
        message = (f"Cancelled. Your paid features stay on until "
                   f"{result.access_until:%d %B %Y}.")
    else:
        message = "Cancelled. Your paid features have ended."
    return CancelResponse(status=result.status,
                          cancel_at_period_end=result.cancel_at_period_end,
                          access_until=result.access_until, message=message)


# --- receipts ---------------------------------------------------------------

@router.get("/invoices", response_model=list[InvoiceResponse],
            summary="My invoices")
def my_invoices(
    limit: int = Query(default=50, ge=1, le=200),
    founder: Founder = Depends(get_founder_record),
    repository=Depends(get_subscription_repository),
) -> list[InvoiceResponse]:
    return [InvoiceResponse(
        invoice_id=r["invoice_id"], invoice_number=r["invoice_number"],
        gateway_invoice_id=r["gateway_invoice_id"], amount_inr=float(r["amount_inr"]),
        tax_amount_inr=float(r["tax_amount_inr"]) if r["tax_amount_inr"] is not None else None,
        total_amount_inr=float(r["total_amount_inr"]), currency=r["currency"],
        status=r["status"], invoice_url=r["invoice_url"], issued_at=r["issued_at"],
        paid_at=r["paid_at"],
    ) for r in repository.list_invoices(founder.founder_id, limit=limit)]


@router.get("/history", response_model=list[PaymentHistoryResponse],
            summary="My payment history")
def my_payments(
    limit: int = Query(default=50, ge=1, le=200),
    founder: Founder = Depends(get_founder_record),
    repository=Depends(get_subscription_repository),
) -> list[PaymentHistoryResponse]:
    """Every payment, including the failed ones.

    Failures are shown rather than filtered out on purpose: a founder whose
    renewal did not go through needs to see that, with the reason, on the page
    where they would fix it. Hiding it is how someone discovers a lapsed card
    by losing access.
    """
    rows = repository.list_payments(founder.founder_id, limit=limit)
    out = []
    for r in rows:
        plan = _plan_for(r["plan_tier"])
        out.append(PaymentHistoryResponse(
            payment_id=r["payment_id"], amount_inr=float(r["amount_inr"]),
            currency=r["currency"], status=r["status"], plan_tier=r["plan_tier"],
            plan_name=plan.name if plan else None, failure_reason=r["failure_reason"],
            paid_at=r["paid_at"], refunded_at=r["refunded_at"], created_at=r["created_at"]))
    return out


# --- billing identity -------------------------------------------------------

@router.get("/billing-profile", response_model=BillingProfileResponse,
            summary="My billing name, GSTIN and address")
def get_billing_profile(
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_billing_profile_service),
) -> BillingProfileResponse:
    profile = service.get(founder.founder_id)
    if profile is None:
        # An empty profile rather than a 404: "you have not filled this in" is
        # the normal state for most founders, and a 404 would make the client
        # branch on an error to render a blank form.
        return BillingProfileResponse(
            customer_type="individual", business_name=None, gstin=None,
            billing_address=None, billing_city=None, billing_state=None,
            billing_pincode=None, billing_country="IN", is_invoice_ready=False)
    return _profile_response(profile)


@router.put("/billing-profile", response_model=BillingProfileResponse,
            summary="Save my billing name, GSTIN and address")
def save_billing_profile(
    payload: BillingProfileRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_billing_profile_service),
) -> BillingProfileResponse:
    profile = service.save(
        founder.founder_id, customer_type=payload.customer_type,
        business_name=payload.business_name, gstin=payload.gstin,
        billing_address=payload.billing_address, billing_city=payload.billing_city,
        billing_state=payload.billing_state, billing_pincode=payload.billing_pincode,
        billing_country=payload.billing_country)
    return _profile_response(profile)


# --- helpers ----------------------------------------------------------------

def _plan_for(tier_value: str | None):
    if not tier_value:
        return None
    try:
        return PLANS[PlanTier(tier_value)]
    except (ValueError, KeyError):
        return None


def _profile_response(profile) -> BillingProfileResponse:
    return BillingProfileResponse(
        customer_type=profile.customer_type, business_name=profile.business_name,
        gstin=profile.gstin, billing_address=profile.billing_address,
        billing_city=profile.billing_city, billing_state=profile.billing_state,
        billing_pincode=profile.billing_pincode, billing_country=profile.billing_country,
        is_invoice_ready=profile.is_invoice_ready)


def _entitlement(founder: Founder, record: SubscriptionRecord | None) -> dict:
    """What access this founder actually has, and until when.

    `plan` comes from `founders.plan_type` -- the one source of truth every
    feature gate reads -- and NOT from the subscription's own `plan_type`. The
    two agree in the normal case; where they differ, the subscription row is a
    billing record and the founder column is the entitlement, and reporting
    the billing record as access would tell a founder whose charge failed that
    they still have Pro.

    `access_until` is null for a one-time purchase, which buys a deliverable
    rather than a period and therefore never expires.
    """
    tier_value = getattr(founder, "plan_type", None) or PlanTier.FREE.value
    plan = _plan_for(tier_value)
    access_until = record.access_until if record else None
    return {
        "plan": tier_value,
        "plan_name": plan.name if plan else tier_value,
        "is_paid": bool(plan and plan.is_paid),
        "access_until": access_until.isoformat() if access_until else None,
        "access_start": record.activated_at.isoformat()
        if record and record.activated_at else None,
    }
