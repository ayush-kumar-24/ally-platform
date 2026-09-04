"""Founder-facing payments endpoints.

    POST /payments/checkout    start a Razorpay order for a paid plan

This is the only payments endpoint a founder's own token can reach: nothing
here grants a plan. `POST /payments/checkout` only ever creates a *pending*
payment and hands back what the frontend needs to open Razorpay's Checkout.js
widget -- the plan itself is granted by the signed webhook
(app/api/v1/webhooks/razorpay.py), never from anything a founder's browser
can claim on its own.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

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


class CheckoutResponse(BaseModel):
    payment_id: int
    order_id: str
    amount_paise: int
    currency: str
    key_id: str

    @classmethod
    def from_domain(cls, s: CheckoutSession) -> "CheckoutResponse":
        return cls(payment_id=s.payment_id, order_id=s.order_id, amount_paise=s.amount_paise,
                   currency=s.currency, key_id=s.key_id)


def get_payment_service(db=Depends(get_db)):
    return container.payment_service(db)


@router.post("/checkout", response_model=CheckoutResponse,
            summary="Start a Razorpay order for a paid plan")
def start_checkout(
    payload: CheckoutRequest,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
) -> CheckoutResponse:
    session = service.start_checkout(founder.founder_id, payload.tier)
    return CheckoutResponse.from_domain(session)
