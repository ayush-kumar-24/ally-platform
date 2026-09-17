"""Founder-facing payments endpoints.

    POST /payments/checkout           start a Razorpay order for a paid plan
    POST /payments/confirm            settle a just-paid order without waiting
                                      for the webhook
    POST /payments/coupons/validate   price a discount code before committing
    GET  /payments/states                       the GST states the buyer picks from
    GET  /payments/invoices                     this founder's billing history
    GET  /payments/invoices/{payment_id}        one receipt, as JSON
    GET  /payments/invoices/{payment_id}/pdf    the same receipt, downloadable

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

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db, set_admin_rls_context
from app.models import Founder
from app.payments.gst_states import GST_STATE_CODES
from app.payments.invoice import Invoice, InvoiceNotAvailable
from app.payments.invoice_html import build_invoice_html
from app.payments.invoice_pdf import InvoiceRendererUnavailable, get_or_render_pdf
from app.payments.models import (
    BusinessIdentity,
    CheckoutSession,
    PurchaseType,
    WebhookOutcome,
)
from app.plans.catalog import PlanTier

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: PlanTier
    # A CODE, never an amount. The price is the catalog's to decide; see
    # PaymentService.start_checkout.
    coupon_code: str | None = Field(default=None, max_length=40)
    # The founder's state, which is the GST place of supply. Optional at the
    # API so an older frontend keeps working: a payment with no state still
    # succeeds and simply yields an invoice with IGST and no place of supply
    # claimed. Never an amount and never a tax figure -- the browser says WHERE
    # the supply went, and the backend decides what that costs in tax.
    billing_state: str | None = Field(default=None, max_length=60)
    # Who is buying. Optional so an older frontend keeps working -- such a
    # payment records no purchase type and renders the personal layout, which
    # is what those founders were already getting.
    #
    # It decides WHO THE INVOICE IS ADDRESSED TO and nothing else: both kinds
    # of buyer pay the same price for the same plan and are charged the same
    # GST. Business simply means the document carries the company's own
    # registration, so the company can claim input credit on it.
    purchase_type: PurchaseType | None = None
    # Required when purchase_type is business; ignored otherwise. Validated
    # server-side, including that the GSTIN's own state matches billing_state
    # -- see PaymentService._checked_business_identity.
    business_gstin: str | None = Field(default=None, max_length=20)
    business_name: str | None = Field(default=None, max_length=200)
    business_address: str | None = Field(default=None, max_length=500)


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
    # The identity object is assembled only for a business purchase, so the
    # service is never handed half a business on a personal checkout.
    business = None
    if payload.purchase_type == PurchaseType.BUSINESS:
        business = BusinessIdentity(
            gstin=payload.business_gstin or "",
            legal_name=payload.business_name or "",
            address=payload.business_address,
        )

    session = service.start_checkout(founder.founder_id, payload.tier,
                                     coupon_code=payload.coupon_code,
                                     buyer_state=payload.billing_state,
                                     purchase_type=payload.purchase_type,
                                     business=business)
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


# ---------------------------------------------------------------------------
# Invoices / receipts
#
# Three views of ONE document. The list, the JSON detail and the PDF are all
# built by PaymentService.get_invoice / list_invoices from the same payments
# row, so the figure a founder reads on the billing page is by construction the
# figure printed on the file they download. The billing page used to render a
# hardcoded table of four invented invoices with a PDF button that did nothing;
# these endpoints are what that placeholder was waiting for.
#
# OWNERSHIP is enforced in the repository's WHERE clause, not here -- see
# PaymentRepository.get_invoice_source. A receipt carries a name, an email and
# an amount, so "route forgot to check the owner" is not a mistake this code
# should be able to make.
# ---------------------------------------------------------------------------


class GstStateResponse(BaseModel):
    name: str
    code: str


@router.get("/states", response_model=list[GstStateResponse],
            summary="The states a founder picks their place of supply from")
def list_gst_states() -> list[GstStateResponse]:
    """Served rather than duplicated in the frontend.

    The checkout dropdown and the CGST/SGST-vs-IGST decision have to agree on
    the spelling of every state, and two hand-maintained lists eventually will
    not. This is the same dict `build_invoice` compares against.
    """
    return [GstStateResponse(name=name, code=code)
            for name, code in GST_STATE_CODES.items()]


class InvoiceTaxResponse(BaseModel):
    percent: float
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    total_tax: float
    #: Null when the payment predates collecting the buyer's state, in which
    #: case the split fell back to IGST and no place of supply is claimed.
    place_of_supply: str | None = None
    place_of_supply_code: str | None = None


class InvoiceResponse(BaseModel):
    """Rupees, not paise -- this is display copy, and every other price the
    billing page renders is in rupees.

    `is_tax_invoice` is the only field the UI needs to branch on: false means
    no GSTIN is configured, the document is a payment receipt, and `tax` is
    null. The UI must not infer a tax split from the absence of one.
    """

    payment_id: int
    number: str
    document_title: str
    issued_at: datetime | None
    paid_at: datetime | None
    status: str
    description: str
    plan_tier: str
    billing_cycle: str
    currency: str
    amount_inr: float
    list_amount_inr: float | None = None
    discount_inr: float | None = None
    coupon_code: str | None = None
    #: Who bought it. The billing page uses this to label the row; the
    #: document itself is what actually differs.
    is_business: bool = False
    buyer_gstin: str | None = None
    buyer_legal_name: str | None = None
    is_tax_invoice: bool
    tax: InvoiceTaxResponse | None = None
    payment_reference: str | None = None
    order_reference: str | None = None

    @classmethod
    def from_domain(cls, payment_id: int, inv: Invoice) -> "InvoiceResponse":
        tax = None
        if inv.tax is not None:
            tax = InvoiceTaxResponse(
                percent=float(inv.tax.percent), taxable_value=float(inv.tax.taxable_value),
                cgst=float(inv.tax.cgst), sgst=float(inv.tax.sgst), igst=float(inv.tax.igst),
                total_tax=float(inv.tax.total_tax),
                place_of_supply=inv.tax.place_of_supply,
                place_of_supply_code=inv.tax.place_of_supply_code)
        return cls(
            payment_id=payment_id, number=inv.number, document_title=inv.document_title,
            issued_at=inv.issued_at, paid_at=inv.paid_at, status=inv.status,
            description=inv.description, plan_tier=inv.plan_tier,
            billing_cycle=inv.billing_cycle, currency=inv.currency,
            amount_inr=float(inv.gross_amount),
            list_amount_inr=float(inv.list_amount) if inv.list_amount is not None else None,
            discount_inr=float(inv.discount) if inv.discount is not None else None,
            coupon_code=inv.coupon_code, is_tax_invoice=inv.is_tax_invoice, tax=tax,
            is_business=inv.is_business, buyer_gstin=inv.buyer_gstin,
            buyer_legal_name=inv.buyer_legal_name,
            payment_reference=inv.payment_reference, order_reference=inv.order_reference)


def _owned_invoice(service, founder: Founder, payment_id: int) -> Invoice:
    """This founder's invoice, or the right refusal.

    404 for "not yours or not there" -- one answer for both, so the endpoint
    cannot be used to discover which payment ids exist. 409 for a payment that
    is real and this founder's but not captured: the document is not wrong, it
    does not exist YET, and a founder mid-checkout should be told to wait
    rather than told their payment is missing.
    """
    try:
        invoice = service.get_invoice(founder.founder_id, payment_id)
    except InvoiceNotAvailable as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This payment has not been captured yet, so there is no receipt for "
            "it. If you have just paid, try again in a moment.",
        ) from exc
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment.")
    return invoice


@router.get("/invoices", response_model=list[InvoiceResponse],
            summary="This founder's billing history")
def list_invoices(
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
) -> list[InvoiceResponse]:
    """Captured and refunded payments only.

    A pending row is an abandoned or still-settling checkout, and listing one
    as billing history would show a founder a charge they may never have been
    made -- the one thing a payments list must never do.
    """
    return [InvoiceResponse.from_domain(payment_id, inv)
            for payment_id, inv in service.list_invoices(founder.founder_id)]


@router.get("/invoices/{payment_id}", response_model=InvoiceResponse,
            summary="One receipt, as JSON")
def get_invoice(
    payment_id: int,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
) -> InvoiceResponse:
    return InvoiceResponse.from_domain(payment_id,
                                       _owned_invoice(service, founder, payment_id))


@router.get("/invoices/{payment_id}/document", response_class=Response,
            summary="The receipt as HTML -- the same document the PDF is made of")
def get_invoice_document(
    payment_id: int,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
) -> Response:
    """Served so the on-screen receipt and the downloaded PDF cannot drift.

    A React component re-implementing this layout is exactly how the report PDF
    diverged from the screen once already; there is one template here, and both
    outputs come out of it.
    """
    html = build_invoice_html(_owned_invoice(service, founder, payment_id))
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/invoices/{payment_id}/pdf", response_class=Response,
            summary="Download the receipt as a PDF")
def download_invoice_pdf(
    payment_id: int,
    founder: Founder = Depends(get_founder_record),
    service=Depends(get_payment_service),
) -> Response:
    """The stored copy if there is one, else rendered and kept -- never a
    substitute document.

    503 rather than a plainer fallback PDF when the renderer is down, for the
    same reason report exports do it (app/api/v1/reports/pdf_delivery.py): a
    founder who downloads during a blip and receives a different-looking
    document has no way to know it, and this one is a financial record. A
    missing receipt is recoverable by pressing the button again; a wrong one
    that looks fine is not.
    """
    invoice = _owned_invoice(service, founder, payment_id)
    try:
        pdf = get_or_render_pdf(service.repository, invoice, payment_id=payment_id,
                                founder_id=founder.founder_id)
    except InvoiceRendererUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "We could not produce your receipt PDF just now. Nothing is wrong "
            "with your payment -- please try again in a few minutes.",
            headers={"Retry-After": "120"},
        ) from exc

    # The number, not the payment id: this is the name the file carries into a
    # founder's accounts, and slashes are not legal in one.
    filename = f"{invoice.number.replace('/', '-')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
