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
    # Set only when a coupon was applied. `amount_paise` is always what
    # Razorpay will actually charge, so a client that ignores these three
    # fields still shows and charges the right number; they exist so the order
    # summary can show the founder what they saved.
    list_amount_paise: int | None = None
    discount_paise: int | None = None
    coupon_code: str | None = None


class WebhookOutcome:
    """Plain string constants, not an Enum -- a route handler puts one
    straight into a JSON response without needing `.value`."""

    CAPTURED = "captured"
    ALREADY_PROCESSED = "already_processed"
    # Razorpay itself says this payment is not (yet) captured. Only
    # PaymentService.confirm_checkout produces it: the webhook is told about
    # captures, but a founder can ask about a payment still settling.
    NOT_CAPTURED = "not_captured"
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
    #: The tier this payment was priced for, written when the order was
    #: created. None on rows predating that column -- see PaymentService for
    #: what happens then. It is deliberately OUR copy: the gateway's notes
    #: come back through the browser, which must never get to choose the plan
    #: it is granted.
    plan_tier: str | None = None


@dataclass(frozen=True)
class WebhookResult:
    outcome: str
    payment_id: int | None = None
    founder_id: int | None = None
    plan: str | None = None
    granted_at: datetime | None = None
