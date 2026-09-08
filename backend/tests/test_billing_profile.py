"""Billing identity validation.

Refused at WRITE time on purpose. A malformed GSTIN discovered on an issued
invoice is one the customer cannot claim input credit against, and by then the
invoice exists -- an invoice cannot be reassigned to different details as
easily as a form can be corrected.

Nothing here computes tax. Guide step 14 is explicit that the GST treatment,
the rate and whether Razorpay's document is a compliant tax invoice are the
CA's to confirm; this module collects and validates the INPUTS that answer
needs, and a number this codebase invented would be worse than the absence of
one because it would look authoritative.
"""

from __future__ import annotations

import pytest

from app.payments.billing_profile import BillingProfile, BillingProfileService
from app.payments.errors import InvalidBillingProfileError

VALID_GSTIN = "29ABCDE1234F1Z5"


class FakeRepository:
    def __init__(self):
        self.rows = {}

    def get(self, founder_id):
        return self.rows.get(founder_id)

    def upsert(self, founder_id, **fields):
        self.rows[founder_id] = BillingProfile(founder_id=founder_id, **fields)
        return self.rows[founder_id]


@pytest.fixture
def service():
    return BillingProfileService(FakeRepository())


def test_an_individual_needs_no_business_details(service):
    profile = service.save(1, customer_type="individual", billing_address="1 Road",
                           billing_state="Karnataka", billing_pincode="560001")
    assert profile.customer_type == "individual"
    assert profile.gstin is None
    assert profile.is_invoice_ready is True


def test_a_business_must_name_itself(service):
    with pytest.raises(InvalidBillingProfileError):
        service.save(1, customer_type="business", gstin=VALID_GSTIN)


def test_a_gstin_is_normalised_before_it_is_stored(service):
    """Lower case with a stray space is the same GSTIN. Storing it verbatim
    would make it fail every later comparison for a reason the founder cannot
    see on their own screen."""
    profile = service.save(1, customer_type="business", business_name="GoXL",
                           gstin="  29abcde1234f1z5 ")
    assert profile.gstin == VALID_GSTIN


@pytest.mark.parametrize("bad", [
    "29ABCDE1234F1Z",       # too short
    "29ABCDE1234F1Z55",     # too long
    "2XABCDE1234F1Z5",      # state code is not digits
    "29ABCDE1234F1X5",      # the mandatory 'Z' is missing
    "ABCDEFGHIJKLMNO",      # not a GSTIN at all
])
def test_a_malformed_gstin_is_refused(service, bad):
    with pytest.raises(InvalidBillingProfileError):
        service.save(1, customer_type="business", business_name="GoXL", gstin=bad)


def test_a_gstin_with_a_state_code_that_is_not_a_state_is_refused(service):
    """'00ABCDE1234F1Z5' has exactly the right SHAPE. The format check alone
    passes it, and it would reach an invoice as a place of supply that does not
    exist."""
    with pytest.raises(InvalidBillingProfileError) as exc:
        service.save(1, customer_type="business", business_name="GoXL",
                     gstin="00ABCDE1234F1Z5")
    assert "state code" in str(exc.value)


def test_an_individual_cannot_hold_a_gstin(service):
    """A GSTIN belongs to a registered entity. Accepting one here would put a
    GSTIN on an invoice that names no business, which is not a document anyone
    can use."""
    with pytest.raises(InvalidBillingProfileError):
        service.save(1, customer_type="individual", gstin=VALID_GSTIN)


def test_a_bad_pincode_is_refused(service):
    with pytest.raises(InvalidBillingProfileError):
        service.save(1, customer_type="individual", billing_pincode="56001")


def test_an_unknown_customer_type_is_refused(service):
    with pytest.raises(InvalidBillingProfileError):
        service.save(1, customer_type="enterprise")


def test_a_business_is_not_invoice_ready_without_its_gstin_and_address(service):
    """Surfaced BEFORE checkout so the founder is prompted while it can still
    change an invoice."""
    partial = service.save(1, customer_type="business", business_name="GoXL")
    assert partial.is_invoice_ready is False

    complete = service.save(1, customer_type="business", business_name="GoXL",
                            gstin=VALID_GSTIN, billing_address="1 Road",
                            billing_state="Karnataka", billing_pincode="560001")
    assert complete.is_invoice_ready is True


def test_saving_twice_replaces_rather_than_duplicates(service):
    """One row per founder. Two would make "which address do we invoice"
    genuinely ambiguous."""
    service.save(1, customer_type="individual", billing_state="Kerala")
    service.save(1, customer_type="individual", billing_state="Goa")
    assert service.get(1).billing_state == "Goa"
    assert len(service.repository.rows) == 1
