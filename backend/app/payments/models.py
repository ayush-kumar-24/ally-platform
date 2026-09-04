"""Payment domain DTOs -- what PaymentService hands back to its callers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CheckoutSession:
    """Everything the frontend needs to hand to Razorpay's Checkout.js widget.
    `key_id` is the *public* key -- safe to return to the browser; the key
    secret and webhook secret never leave the backend."""

    payment_id: int
    order_id: str
    amount_paise: int
    currency: str
    key_id: str


class WebhookOutcome:
    """Plain string constants, not an Enum -- a route handler puts one
    straight into a JSON response without needing `.value`."""

    CAPTURED = "captured"
    ALREADY_PROCESSED = "already_processed"
    FAILED_RECORDED = "failed_recorded"
    IGNORED_EVENT = "ignored_event"
    UNKNOWN_PAYMENT = "unknown_payment"


@dataclass(frozen=True)
class PaymentRecord:
    """One row of `payments`, as much as the service layer needs of it."""

    payment_id: int
    founder_id: int
    status: str
    gateway_order_id: str | None
    gateway_payment_id: str | None
    amount_inr: int
    subscription_id: int | None


@dataclass(frozen=True)
class WebhookResult:
    outcome: str
    payment_id: int | None = None
    founder_id: int | None = None
    plan: str | None = None
    granted_at: datetime | None = None
