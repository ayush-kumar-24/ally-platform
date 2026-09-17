"""The receipt a founder downloads after paying.

Same approach as test_payments_service.py: plain hand-written doubles, no
gateway and no database, so these can assert the properties that actually
matter about a financial document.

Those properties, in order of how much they would cost to get wrong:

  1. the total on the document is the amount Razorpay charged, always;
  2. GST is backed OUT of that total, never added on top of it;
  3. the three tax figures reconcile to the total exactly, to the paisa;
  4. with no GSTIN configured it is a RECEIPT and shows no tax at all;
  5. the invoice number is stable -- the same payment never gets two;
  6. a pending payment has no document, and says so as a distinct condition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.config import settings
from app.payments.invoice import (
    InvoiceNotAvailable,
    build_invoice,
    compute_tax,
    invoice_number,
)
from app.payments.invoice_html import build_invoice_html
from app.payments.models import InvoiceSource

PAID_AT = datetime(2026, 3, 14, 9, 30, tzinfo=timezone.utc)


def source(**overrides) -> InvoiceSource:
    base = dict(
        payment_id=123, founder_id=7, status="success", amount_inr=Decimal("999.00"),
        currency="INR", plan_tier="pro", gateway_order_id="order_abc",
        gateway_payment_id="pay_abc", paid_at=PAID_AT, created_at=PAID_AT,
        invoice_number=None, list_amount_inr=None, discount_inr=None,
        coupon_code=None, billing_cycle="monthly",
    )
    base.update(overrides)
    return InvoiceSource(**base)


def build(**overrides):
    return build_invoice(source(**overrides), founder_name="Asha Rao",
                         founder_email="asha@example.com")


@pytest.fixture
def no_gstin(monkeypatch):
    monkeypatch.setattr(settings, "INVOICE_SELLER_GSTIN", "")
    return settings


@pytest.fixture
def with_gstin(monkeypatch):
    monkeypatch.setattr(settings, "INVOICE_SELLER_GSTIN", "29AABCU9603R1ZM")
    monkeypatch.setattr(settings, "INVOICE_GST_PERCENT", 18.0)
    return settings


# --- the total is the amount charged -------------------------------------

def test_total_is_the_amount_charged_not_a_recomputed_catalog_price(no_gstin):
    """The catalog says Pro is Rs 999 today. This payment took Rs 749, because
    that is what the price was when it was made. The receipt must say 749 --
    a document that reprices itself from today's catalog is a document that
    tells a founder they paid something they did not."""
    invoice = build(amount_inr=Decimal("749.00"))
    assert invoice.gross_amount == Decimal("749.00")


def test_gst_is_backed_out_of_the_total_never_added_to_it(with_gstin):
    """The single most expensive mistake available here: Rs 999 charged must
    stay Rs 999 on the document, with the tax found inside it."""
    invoice = build(amount_inr=Decimal("999.00"))
    assert invoice.gross_amount == Decimal("999.00")
    assert invoice.tax is not None
    assert invoice.tax.taxable_value < Decimal("999.00")
    assert invoice.tax.taxable_value + invoice.tax.total_tax == Decimal("999.00")


def test_tax_components_reconcile_to_the_paisa_across_awkward_amounts(with_gstin):
    """Rounding must never produce three numbers that do not add up -- that is
    what an accountant notices, and it is the sort of error that shows up on
    exactly one invoice in a thousand."""
    for amount in ["1.00", "199.00", "499.00", "999.00", "1000.01", "7777.77"]:
        tax = compute_tax(Decimal(amount), percent=Decimal("18"), intra_state=False)
        assert tax.taxable_value + tax.total_tax == Decimal(amount), amount


def test_intra_state_split_halves_add_back_to_the_whole_tax():
    tax = compute_tax(Decimal("999.00"), percent=Decimal("18"), intra_state=True)
    assert tax.cgst + tax.sgst == tax.total_tax
    assert tax.igst == 0
    assert tax.taxable_value + tax.total_tax == Decimal("999.00")


def test_inter_state_puts_everything_in_igst():
    tax = compute_tax(Decimal("999.00"), percent=Decimal("18"), intra_state=False)
    assert tax.cgst == 0 and tax.sgst == 0
    assert tax.igst == tax.total_tax


# --- receipt vs tax invoice ----------------------------------------------

def test_without_a_gstin_it_is_a_receipt_with_no_tax_breakdown(no_gstin):
    """A tax split printed without a registration number is a split nobody can
    claim credit against -- worse than showing none, because it looks claimable."""
    invoice = build()
    assert invoice.is_tax_invoice is False
    assert invoice.tax is None
    assert invoice.sac_code is None
    assert invoice.document_title == "Payment Receipt"


def test_a_receipt_says_in_words_that_it_is_not_a_tax_invoice(no_gstin):
    html = build_invoice_html(build())
    assert "not a tax invoice" in html
    assert "GST" in html  # says so explicitly rather than staying silent


def test_with_a_gstin_it_is_a_tax_invoice_carrying_the_sac_code(with_gstin):
    invoice = build()
    assert invoice.is_tax_invoice is True
    assert invoice.document_title == "Tax Invoice"
    assert invoice.sac_code == "998314"
    assert invoice.seller_gstin == "29AABCU9603R1ZM"


# --- numbering ------------------------------------------------------------

def test_the_number_is_derived_so_the_same_payment_never_gets_two():
    assert invoice_number(123, PAID_AT) == invoice_number(123, PAID_AT)
    assert invoice_number(123, PAID_AT) == "ALLY/2026/000123"


def test_an_already_issued_number_is_reused_not_recomputed(no_gstin):
    """Even if the derivation rule changed underneath it, a number a founder is
    already holding a copy of must not be superseded."""
    invoice = build(invoice_number="LEGACY/2025/000001")
    assert invoice.number == "LEGACY/2025/000001"


# --- what is and is not invoiceable ---------------------------------------

@pytest.mark.parametrize("status", ["pending", "failed"])
def test_an_uncaptured_payment_has_no_document(status, no_gstin):
    with pytest.raises(InvoiceNotAvailable):
        build(status=status)


def test_a_refunded_payment_still_has_a_document(no_gstin):
    """The charge happened and the founder's bank statement has a line for it.
    Hiding the receipt afterwards leaves them with nothing to match it to."""
    invoice = build(status="refunded")
    assert invoice.status == "refunded"
    assert invoice.gross_amount == Decimal("999.00")


# --- discounts ------------------------------------------------------------

def test_a_discount_shows_the_list_price_and_the_saving(no_gstin):
    invoice = build(amount_inr=Decimal("799.00"), list_amount_inr=Decimal("999.00"),
                    discount_inr=Decimal("200.00"), coupon_code="LAUNCH20")
    assert invoice.list_amount == Decimal("999.00")
    assert invoice.discount == Decimal("200.00")
    assert invoice.coupon_code == "LAUNCH20"
    # The charged amount is still the grand total. The discount is context.
    assert invoice.gross_amount == Decimal("799.00")

    html = build_invoice_html(invoice)
    assert "LAUNCH20" in html
    assert "799.00" in html


def test_an_undiscounted_payment_carries_no_discount_fields(no_gstin):
    """Set-or-None, not a redundant copy of the amount -- the same rule
    payments.list_amount_inr follows, so "was this discounted?" is answerable
    by the field being present."""
    invoice = build()
    assert invoice.list_amount is None
    assert invoice.discount is None


# --- the rendered document ------------------------------------------------

def test_the_html_is_self_contained_because_gotenberg_has_no_network(no_gstin):
    """An external stylesheet or webfont renders as nothing inside the
    headless-Chromium sidecar, and silently."""
    html = build_invoice_html(build())
    assert "<link" not in html
    assert "<script" not in html
    assert "http://" not in html and "https://" not in html


def test_the_founder_and_the_amount_are_on_the_document(no_gstin):
    html = build_invoice_html(build())
    assert "Asha Rao" in html
    assert "asha@example.com" in html
    assert "999.00" in html
    assert "ALLY/2026/000123" in html


def test_amounts_are_grouped_the_indian_way(no_gstin):
    html = build_invoice_html(build(amount_inr=Decimal("125000.00")))
    assert "1,25,000.00" in html


def test_a_founder_supplied_name_cannot_inject_markup(no_gstin):
    """The name comes from a profile field the founder types into."""
    invoice = build_invoice(source(), founder_name="<script>alert(1)</script>",
                            founder_email="x@example.com")
    html = build_invoice_html(invoice)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_a_one_time_purchase_is_not_labelled_a_subscription(no_gstin):
    assert build(billing_cycle="one_time").billing_cycle == "One-time purchase"
    assert build(billing_cycle="monthly").billing_cycle == "Monthly subscription"


def test_a_retired_tier_still_renders_rather_than_raising(no_gstin):
    """Catalogs get edited years after a payment was taken."""
    invoice = build(plan_tier="legacy_gold")
    assert "legacy_gold" in invoice.description


# --- render + store -------------------------------------------------------

class FakeInvoiceRepo:
    """Records what was written, so the tests can assert on the writes rather
    than on a database."""

    def __init__(self, *, stored_key=None):
        self.stored_key = stored_key
        self.numbers = []
        self.urls = []

    def invoice_storage_key(self, payment_id, *, founder_id):
        return self.stored_key

    def record_invoice_number(self, payment_id, *, founder_id, number):
        self.numbers.append((payment_id, founder_id, number))

    def record_invoice_url(self, payment_id, *, founder_id, url):
        self.urls.append((payment_id, founder_id, url))


def test_a_stored_receipt_is_served_not_re_rendered(monkeypatch, no_gstin):
    """A receipt is a record of a transaction, not regenerated content: the
    same download in March and in November must hand back the same bytes, not
    whatever the template looks like by then."""
    from app.payments import invoice_pdf

    monkeypatch.setattr(invoice_pdf, "stored_pdf", lambda key: b"%PDF-stored")

    def fail(*a, **k):
        raise AssertionError("re-rendered a receipt that was already stored")

    monkeypatch.setattr(invoice_pdf, "render_pdf", fail)

    repo = FakeInvoiceRepo(stored_key="invoices/123/invoice.pdf")
    pdf = invoice_pdf.get_or_render_pdf(repo, build(), payment_id=123, founder_id=7)
    assert pdf == b"%PDF-stored"


def test_a_renderer_outage_raises_rather_than_substituting_a_document(monkeypatch, no_gstin):
    """No fallback document, for the same reason report export has none: a
    founder who downloads during a blip and gets a different document has no
    way to know, and this one is a financial record."""
    from app.api.v1.reports.gotenberg import GotenbergError
    from app.payments import invoice_pdf

    monkeypatch.setattr(invoice_pdf, "stored_pdf", lambda key: None)
    monkeypatch.setattr(invoice_pdf, "render_pdf",
                        lambda *a, **k: (_ for _ in ()).throw(GotenbergError("down")))

    repo = FakeInvoiceRepo()
    with pytest.raises(invoice_pdf.InvoiceRendererUnavailable):
        invoice_pdf.get_or_render_pdf(repo, build(), payment_id=123, founder_id=7)
    # Nothing recorded: the request stays retryable exactly as it was.
    assert repo.numbers == [] and repo.urls == []


def test_the_number_is_recorded_against_the_owning_founder(monkeypatch, no_gstin):
    from app.payments import invoice_pdf

    monkeypatch.setattr(invoice_pdf, "stored_pdf", lambda key: None)
    monkeypatch.setattr(invoice_pdf, "render_pdf", lambda *a, **k: b"%PDF-new")
    monkeypatch.setattr(invoice_pdf, "_storage", lambda: None)

    repo = FakeInvoiceRepo()
    pdf = invoice_pdf.get_or_render_pdf(repo, build(), payment_id=123, founder_id=7)
    assert pdf == b"%PDF-new"
    assert repo.numbers == [(123, 7, "ALLY/2026/000123")]


def test_a_receipt_is_still_served_when_storage_is_unconfigured(monkeypatch, no_gstin):
    """Local dev and CI have no bucket. Storage makes downloads cheap; it is
    not what makes them correct."""
    from app.payments import invoice_pdf

    monkeypatch.setattr(invoice_pdf, "stored_pdf", lambda key: None)
    monkeypatch.setattr(invoice_pdf, "render_pdf", lambda *a, **k: b"%PDF-new")
    monkeypatch.setattr(invoice_pdf, "_storage", lambda: None)

    repo = FakeInvoiceRepo()
    assert invoice_pdf.get_or_render_pdf(repo, build(), payment_id=123,
                                         founder_id=7) == b"%PDF-new"
    assert repo.urls == []  # nothing to point at
