"""The invoice/receipt a founder can download after paying.

WHERE THE NUMBERS COME FROM. Every figure on this document is read back out of
the `payments` row that Razorpay actually charged against -- never recomputed
from the plan catalog, and never taken from anything the browser sent. The
catalog moves (prices change, coupons expire, a tier is renamed) and a receipt
issued in March must still say what was charged in March. So the catalog is
consulted for ONE thing only: the display name of the tier, and even that falls
back to the stored tier string when the tier no longer exists.

RECEIPT vs TAX INVOICE. With no `INVOICE_SELLER_GSTIN` configured this renders
as a plain payment receipt: a record that money was taken, with no tax
breakdown. Configure a GSTIN and the same payment renders as a tax invoice with
the GST backed OUT of the amount charged. That direction matters. Razorpay took
a gross rupee figure from the founder; showing tax added on top of it would
state a total that nobody was ever charged.

WHY THE NUMBER IS DERIVED, NOT ALLOCATED. `ALLY/2026/000123` is a pure function
of the payment id and the year it was paid in. No counter, no sequence table,
no race between two webhooks, and -- the property that actually matters -- the
same payment yields the same invoice number forever, so a founder who
downloads their receipt twice, or an accountant who reconciles it a year later,
sees one document and not two. `payments.invoice_number` is written once on
first issue as the audit trail of that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import settings
from app.core.logger import logger
from app.plans.catalog import PLANS, PlanTier

#: SAC code for "online information and database access or retrieval services",
#: which is what a subscription to this product is. Printed on a tax invoice
#: only -- a receipt carries no tax classification because it claims none.
SAC_CODE = "998314"


def _money(value) -> Decimal:
    """Rupees, rounded the way money is rounded, never the way floats are."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxBreakdown:
    """The GST backed out of a GST-inclusive charge.

    `taxable_value + total_tax == gross`, exactly, by construction: the split
    halves are derived from the total and the last paisa is given to whichever
    component was rounded down, so the document can never print three numbers
    that do not add up.
    """

    percent: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal

    @property
    def total_tax(self) -> Decimal:
        return _money(self.cgst + self.sgst + self.igst)

    @property
    def intra_state(self) -> bool:
        return self.igst == 0


@dataclass(frozen=True)
class Invoice:
    """A rendered-document-ready view of one captured payment."""

    number: str
    issued_at: datetime
    #: False when no GSTIN is configured -- the document is then a receipt and
    #: `tax` is None. Templates branch on this and on nothing else.
    is_tax_invoice: bool

    seller_name: str
    seller_address: str
    seller_email: str
    seller_gstin: str | None
    seller_state: str | None

    buyer_name: str
    buyer_email: str

    description: str
    plan_tier: str
    #: 'One-time purchase' or 'Monthly subscription' -- what the founder bought,
    #: in the words the billing page already uses for it.
    billing_cycle: str

    #: The catalog list price at the time of purchase, set only when a coupon
    #: was applied. None on an undiscounted payment rather than a copy of the
    #: amount charged, so "was this discounted?" is answerable by the field
    #: being set -- the same rule payments.list_amount_inr follows.
    list_amount: Decimal | None
    discount: Decimal | None
    coupon_code: str | None
    #: What Razorpay actually took. The one authoritative figure here.
    gross_amount: Decimal
    currency: str

    tax: TaxBreakdown | None

    payment_reference: str | None
    order_reference: str | None
    paid_at: datetime | None
    status: str

    @property
    def sac_code(self) -> str | None:
        return SAC_CODE if self.is_tax_invoice else None

    @property
    def document_title(self) -> str:
        return "Tax Invoice" if self.is_tax_invoice else "Payment Receipt"


#: A GSTIN is exactly 15 alphanumerics. This is a SHAPE check, not a checksum:
#: it is here to catch a misconfiguration, not to validate a registration.
_GSTIN_SHAPE = re.compile(r"^[0-9A-Z]{15}$")


def _valid_gstin(raw: str | None) -> str | None:
    """The configured GSTIN, or None when there isn't a usable one.

    Not `bool(gstin)`, because "non-empty" is a dangerously low bar for the
    switch that turns a payment receipt into a TAX INVOICE. A .env written as

        INVOICE_SELLER_GSTIN=          # blank = issue receipts

    parses -- in python-dotenv, as this repo's own .env.example did for five
    other keys -- with the COMMENT as the value. Non-empty, so every receipt
    would have silently become a tax invoice claiming a GST split under a
    registration number reading "# blank = issue receipts". Founders would have
    filed them, and nobody would have found out from this end.

    So the shape is checked and anything else is treated as unset, loudly. The
    safe direction is unambiguous here: issuing a receipt when a tax invoice
    was wanted is a config fix, while issuing an invalid tax invoice is a
    document already in somebody's accounts.
    """
    candidate = (raw or "").strip().upper()
    if not candidate:
        return None
    if not _GSTIN_SHAPE.match(candidate):
        logger.error(
            "payments: INVOICE_SELLER_GSTIN is not a 15-character GSTIN; issuing "
            "payment receipts instead of tax invoices until it is corrected",
            extra={"configured_length": len(candidate)},
        )
        return None
    return candidate


def invoice_number(payment_id: int, paid_at: datetime | None) -> str:
    """`ALLY/2026/000123` -- deterministic, so re-issuing is not re-numbering.

    An unpaid row has no year to file under, so it takes the current one; it
    also has no business being invoiced, which is the caller's check to make
    (see `build_invoice`), not this function's.
    """
    year = (paid_at or datetime.now(timezone.utc)).year
    prefix = (settings.INVOICE_NUMBER_PREFIX or "ALLY").strip("/ ")
    return f"{prefix}/{year}/{payment_id:06d}"


def compute_tax(gross: Decimal, *, percent: Decimal, intra_state: bool) -> TaxBreakdown:
    """Back GST out of a GST-INCLUSIVE gross amount.

    taxable = gross * 100 / (100 + percent). Not `gross * percent`, which is
    the mistake this function exists to make impossible: that would invent tax
    on top of a total the founder has already been charged, and every figure
    below it would overstate what they paid.

    Intra-state splits into CGST+SGST, inter-state is a single IGST line. We do
    not record the founder's state of supply, so the caller decides -- and
    today it decides inter-state, which is the reading that does not assert a
    place of supply we never asked for.
    """
    gross = _money(gross)
    if percent <= 0:
        return TaxBreakdown(percent=Decimal("0.00"), taxable_value=gross,
                            cgst=Decimal("0.00"), sgst=Decimal("0.00"), igst=Decimal("0.00"))

    taxable = _money(gross * Decimal(100) / (Decimal(100) + percent))
    # Derived by subtraction rather than computed independently, so the three
    # printed numbers always reconcile to the amount charged even when the
    # rounding of the taxable value went the other way.
    total_tax = _money(gross - taxable)

    if intra_state:
        half = _money(total_tax / 2)
        # The odd paisa goes to CGST. Arbitrary but fixed -- what matters is
        # that cgst + sgst is total_tax and not total_tax +/- 0.01.
        return TaxBreakdown(percent=percent, taxable_value=taxable,
                            cgst=_money(total_tax - half), sgst=half, igst=Decimal("0.00"))
    return TaxBreakdown(percent=percent, taxable_value=taxable,
                        cgst=Decimal("0.00"), sgst=Decimal("0.00"), igst=total_tax)


class InvoiceNotAvailable(Exception):
    """This payment has nothing to invoice yet (or ever).

    A pending payment is the common case and is not an error condition: the
    founder is mid-checkout, or the capture has not landed. The route turns
    this into a 409 rather than a 404, because the payment is real and the
    document will exist shortly.
    """


def build_invoice(source, *, founder_name: str, founder_email: str,
                  issued_at: datetime | None = None) -> Invoice:
    """Assemble the document for one captured payment.

    `source` is an `InvoiceSource` from PaymentRepository -- the payment row
    with the coupon fields and the subscription's billing cycle already joined
    on, so this function does no querying and can be tested with a plain
    object.

    Refunded payments ARE invoiceable and deliberately so: the charge happened,
    the founder's accounts have a record of it, and hiding the document after a
    refund would leave them holding a bank line with nothing to match it to.
    The status travels on the document instead.
    """
    if source.status not in ("success", "refunded"):
        raise InvoiceNotAvailable(
            f"payment {source.payment_id} is {source.status}, not captured"
        )

    gross = _money(source.amount_inr)
    gstin = _valid_gstin(settings.INVOICE_SELLER_GSTIN)
    is_tax_invoice = gstin is not None

    tax = None
    if is_tax_invoice:
        tax = compute_tax(
            gross,
            percent=Decimal(str(settings.INVOICE_GST_PERCENT)),
            # Inter-state: we hold no state of supply for the founder, and
            # asserting one we never collected would be a worse error than the
            # conservative single-line split. See compute_tax.
            intra_state=False,
        )

    # The catalog is consulted for the plan's DISPLAY NAME and nothing else --
    # and even that degrades to the stored tier string, so a tier that is
    # retired or renamed years later still renders a readable document rather
    # than raising on a KeyError.
    plan_name = source.plan_tier or "Plan"
    try:
        plan_name = PLANS[PlanTier(source.plan_tier)].name
    except (ValueError, KeyError):
        pass

    one_time = (source.billing_cycle or "").lower() == "one_time"

    return Invoice(
        number=source.invoice_number or invoice_number(source.payment_id, source.paid_at),
        issued_at=issued_at or source.paid_at or datetime.now(timezone.utc),
        is_tax_invoice=is_tax_invoice,
        seller_name=settings.INVOICE_SELLER_NAME,
        seller_address=settings.INVOICE_SELLER_ADDRESS,
        seller_email=settings.INVOICE_SELLER_EMAIL,
        seller_gstin=gstin or None,
        seller_state=(settings.INVOICE_SELLER_STATE or "").strip() or None,
        buyer_name=founder_name,
        buyer_email=founder_email,
        description=f"GoXL Ally — {plan_name} plan",
        plan_tier=source.plan_tier or "",
        billing_cycle="One-time purchase" if one_time else "Monthly subscription",
        list_amount=_money(source.list_amount_inr) if source.list_amount_inr else None,
        discount=_money(source.discount_inr) if source.discount_inr else None,
        coupon_code=source.coupon_code,
        gross_amount=gross,
        currency=source.currency or "INR",
        tax=tax,
        payment_reference=source.gateway_payment_id,
        order_reference=source.gateway_order_id,
        paid_at=source.paid_at,
        status=source.status,
    )
