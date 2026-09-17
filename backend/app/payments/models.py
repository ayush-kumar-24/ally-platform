"""Payment domain DTOs -- what PaymentService hands back to its callers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PurchaseType(str, Enum):
    """Who a payment was made by, for the purposes of the invoice.

    NOT a pricing tier and NOT a plan: both kinds of buyer pay the same price
    for the same plan and are charged the same GST. What differs is the
    identity the tax invoice is addressed to, and therefore whether the buyer
    can claim input tax credit on it.

    A payment with no purchase_type at all predates the question being asked.
    That is deliberately NOT spelled `PERSONAL`: the invoice renders it with
    the personal layout, because that is what those founders received, but
    "we never asked" stays distinguishable from "they told us personal".
    """

    PERSONAL = "personal"
    BUSINESS = "business"


@dataclass(frozen=True)
class BusinessIdentity:
    """The buyer's own tax identity, for a business purchase.

    Carried as one object rather than three loose arguments so that "a business
    purchase always has all three" is a shape the type system can hold, instead
    of an invariant every caller has to remember.
    """

    gstin: str
    legal_name: str
    address: str | None = None


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
    #: GST ADDED ON TOP, in paise, and the rate it was added at. Non-zero only
    #: on a business purchase, where the catalog price is ex-GST. Zero on a
    #: personal one, whose price already includes the tax -- so `amount_paise`
    #: is what Razorpay charges either way, and a client ignoring these two
    #: fields still shows and charges the right number. They exist so the
    #: summary can show WHY the total moved when "business" was ticked.
    gst_paise: int = 0
    gst_percent: float | None = None


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


@dataclass(frozen=True)
class InvoiceSource:
    """Everything an invoice is made of, read back out of one `payments` row.

    Deliberately wider than PaymentRecord rather than an extension of it:
    PaymentRecord is what the GRANT path needs and every field on it is one the
    service is allowed to act on. This is what the DOCUMENT path needs, and it
    is all history -- the coupon that was applied, the price before it, the
    cycle the subscription was written with. Keeping them apart means a field
    added for a receipt can never quietly become an input to a plan grant.
    """

    payment_id: int
    founder_id: int
    status: str
    amount_inr: object
    currency: str
    plan_tier: str | None
    gateway_order_id: str | None
    gateway_payment_id: str | None
    paid_at: datetime | None
    created_at: datetime | None
    #: Already-issued number, when this payment has been invoiced before. The
    #: builder reuses it rather than deriving a fresh one, so a number that was
    #: once shown to a founder is never superseded -- even if the derivation
    #: rule changes underneath it.
    invoice_number: str | None = None
    list_amount_inr: object | None = None
    discount_inr: object | None = None
    coupon_code: str | None = None
    #: 'personal', 'business', or None for a payment taken before the question
    #: was asked. See PurchaseType.
    purchase_type: str | None = None
    #: The buyer's own registration, on a business purchase. This is what makes
    #: the tax invoice claimable by them -- without it a company has paid GST it
    #: cannot reclaim.
    buyer_gstin: str | None = None
    buyer_legal_name: str | None = None
    buyer_address: str | None = None
    #: The buyer's state at the time of the sale -- the GST place of supply,
    #: frozen on the payment rather than read off the founder, so an invoice
    #: never re-renders under a different tax treatment because the founder
    #: moved. None on payments taken before this was collected.
    buyer_state: str | None = None
    #: From the subscription this payment created: 'one_time' or 'monthly'.
    #: None on a payment whose subscription row is missing, which reads as
    #: monthly -- the conservative default, since a one-time purchase
    #: mislabelled as a subscription is the more alarming direction to get
    #: wrong and this way it cannot happen silently.
    billing_cycle: str | None = None
