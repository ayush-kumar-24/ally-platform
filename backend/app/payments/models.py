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
    # Trial + autopay (app/payments/subscriptions.py).
    TRIAL_STARTED = "trial_started"
    RENEWED = "renewed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RECORDED = "recorded"


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


@dataclass(frozen=True)
class SubscriptionRecord:
    """One row of `subscriptions` that a Razorpay autopay subscription backs."""

    subscription_id: int
    founder_id: int
    plan_type: str
    status: str
    billing_cycle: str | None
    amount_inr: int
    trial_ends_at: datetime | None
    expires_at: datetime | None
    cancelled_at: datetime | None
    gateway_subscription_id: str | None

    @property
    def access_until(self) -> datetime | None:
        """When the plan stops if nothing else is charged: the paid period's end
        once one exists, the trial's end before that. None = no end (a Starter
        month, which is paid once and never lapses)."""
        if self.expires_at is not None:
            return self.expires_at
        if self.status == "active":
            return None
        return self.trial_ends_at


@dataclass(frozen=True)
class TrialCheckout:
    """What the frontend hands Checkout.js to start a trial. `subscription_id`
    is Razorpay's; the widget opens on it instead of an order id."""

    subscription_id: str
    key_id: str
    plan_name: str
    trial_days: int
    trial_amount_paise: int
    plan_amount_paise: int
    first_charge_paise: int
    trial_ends_at: datetime
    recurring: bool
