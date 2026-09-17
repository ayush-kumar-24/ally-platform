"""API tests for POST /payments/checkout.

dependency_overrides inject a fake authenticated founder + a fake
PaymentService, same pattern as test_api_settings_preferences.py -- no DB or
Razorpay account needed. Money-safety logic itself is covered by
test_payments_service.py; the point of these is that the route wires the
founder's own id through correctly and maps errors to the right status codes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_founder_record
from app.api.v1.payments.router import get_coupon_service, get_payment_service
from app.db.session import get_db
from app.main import app
from app.payments.errors import (
    InvalidCheckoutError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
)
from app.payments.errors import PaymentNotFoundError
from app.payments.models import CheckoutSession, WebhookOutcome, WebhookResult

BASE = "/api/v1/payments"


class FakeService:
    def __init__(self, *, session=None, raises=None, confirm_result=None):
        self.session = session
        self.raises = raises
        self.confirm_result = confirm_result
        self.calls = []
        self.state_calls = []
        self.buyer_calls = []
        self.confirm_calls = []

    def start_checkout(self, founder_id, tier, coupon_code=None, buyer_state=None,
                       purchase_type=None, business=None):
        self.calls.append((founder_id, tier, coupon_code))
        self.state_calls.append(buyer_state)
        self.buyer_calls.append((purchase_type, business))
        if self.raises:
            raise self.raises
        return self.session

    def confirm_checkout(self, founder_id, *, order_id, gateway_payment_id, signature=None):
        self.confirm_calls.append((founder_id, order_id, gateway_payment_id, signature))
        if self.raises:
            raise self.raises
        return self.confirm_result


class FakeSession:
    """Enough Session for `set_admin_rls_context` on the confirm route: it
    records the elevation in `info` and, with no transaction open, issues no
    SQL. Keeps these tests DB-free like the rest of the file."""

    def __init__(self):
        self.info = {}

    def in_transaction(self):
        return False


@pytest.fixture
def client():
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(founder_id=7)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    yield SimpleNamespace(http=TestClient(app))
    app.dependency_overrides.pop(get_founder_record, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_payment_service, None)
    app.dependency_overrides.pop(get_coupon_service, None)


def _use(service: FakeService) -> None:
    app.dependency_overrides[get_payment_service] = lambda: service


def test_checkout_requires_authentication():
    """No get_founder_record override installed -- the real dependency chain
    runs and rejects, same guard test_api_admin_panel.py's own
    'without_override' test proves for the admin panel."""
    bare = TestClient(app)
    r = bare.post(f"{BASE}/checkout", json={"tier": "starter"})
    assert r.status_code != 200


def test_checkout_passes_the_authenticated_founders_own_id(client):
    service = FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=45000, currency="INR",
        key_id="rzp_test_key"))
    _use(service)

    r = client.http.post(f"{BASE}/checkout", json={"tier": "starter"})
    assert r.status_code == 200
    assert service.calls == [(7, "starter", None)]


def test_checkout_returns_the_session_the_frontend_needs(client):
    service = FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_abc", amount_paise=99900, currency="INR",
        key_id="rzp_live_key"))
    _use(service)

    body = client.http.post(f"{BASE}/checkout", json={"tier": "pro"}).json()
    # The three coupon fields are null on an undiscounted order rather than
    # absent, so the client reads one shape either way.
    assert body == {"payment_id": 1, "order_id": "order_abc", "amount_paise": 99900,
                    "currency": "INR", "key_id": "rzp_live_key",
                    "list_amount_paise": None, "discount_paise": None,
                    "coupon_code": None}


def test_checkout_rejects_an_unknown_tier(client):
    _use(FakeService())
    r = client.http.post(f"{BASE}/checkout", json={"tier": "enterprise-deluxe"})
    assert r.status_code == 422


def test_checkout_rejects_extra_fields(client):
    _use(FakeService())
    r = client.http.post(f"{BASE}/checkout", json={"tier": "starter", "amount": 1})
    assert r.status_code == 422


def test_checkout_reports_503_when_payments_are_not_configured(client):
    _use(FakeService(raises=PaymentsNotConfiguredError()))
    r = client.http.post(f"{BASE}/checkout", json={"tier": "starter"})
    assert r.status_code == 503


def test_checkout_reports_502_when_the_gateway_refuses_the_order(client):
    _use(FakeService(raises=PaymentGatewayUnavailableError()))
    r = client.http.post(f"{BASE}/checkout", json={"tier": "starter"})
    assert r.status_code == 502
    body = r.json()
    assert body["error"] == "PaymentGatewayUnavailableError"
    assert "payment provider" in body["message"]
    assert body["request_id"]


def test_checkout_reports_422_for_the_free_plan(client):
    _use(FakeService(raises=InvalidCheckoutError("the free plan needs no checkout")))
    r = client.http.post(f"{BASE}/checkout", json={"tier": "free"})
    assert r.status_code == 422


# --- coupons ----------------------------------------------------------------

class FakeCoupons:
    def __init__(self, *, quote=None, raises=None):
        self.quote_result = quote
        self.raises = raises
        self.calls = []

    def quote(self, *, code, tier, founder_id):
        self.calls.append((code, tier, founder_id))
        if self.raises:
            raise self.raises
        return self.quote_result


def _use_coupons(service: FakeCoupons) -> None:
    app.dependency_overrides[get_coupon_service] = lambda: service


def test_validate_returns_the_price_breakdown(client):
    from app.coupons.models import CouponQuote

    _use_coupons(FakeCoupons(quote=CouponQuote(
        code="FOUNDER100", description="First 100", list_amount_inr=999,
        discount_inr=500, payable_inr=499)))

    r = client.http.post(f"{BASE}/coupons/validate",
                         json={"tier": "pro", "code": "founder100"})

    assert r.status_code == 200
    assert r.json() == {"code": "FOUNDER100", "description": "First 100",
                        "list_amount_inr": 999, "discount_inr": 500, "payable_inr": 499}


def test_validate_passes_the_authenticated_founders_own_id(client):
    """Never a founder_id from the body: per-founder redemption limits would be
    trivially bypassable if the caller chose whose limit to check."""
    from app.coupons.models import CouponQuote

    coupons = FakeCoupons(quote=CouponQuote(code="X", description=None, list_amount_inr=1,
                                            discount_inr=0, payable_inr=1))
    _use_coupons(coupons)
    client.http.post(f"{BASE}/coupons/validate", json={"tier": "pro", "code": "x"})

    assert coupons.calls[0][2] == 7


def test_validate_reports_a_rejected_code_as_422_with_the_specific_reason(client):
    from app.coupons.errors import CouponFullyRedeemedError

    _use_coupons(FakeCoupons(raises=CouponFullyRedeemedError()))
    r = client.http.post(f"{BASE}/coupons/validate", json={"tier": "pro", "code": "gone"})

    assert r.status_code == 422
    assert "fully claimed" in r.json()["message"]


def test_validate_rejects_extra_fields(client):
    _use_coupons(FakeCoupons())
    r = client.http.post(f"{BASE}/coupons/validate",
                         json={"tier": "pro", "code": "x", "discount_inr": 900})
    assert r.status_code == 422


def test_checkout_forwards_the_coupon_code(client):
    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=49900, currency="INR",
        key_id="rzp_test_key")))

    client.http.post(f"{BASE}/checkout", json={"tier": "pro", "coupon_code": "founder100"})

    service = app.dependency_overrides[get_payment_service]()
    assert service.calls[0] == (7, "pro", "founder100")


def test_checkout_without_a_coupon_forwards_none(client):
    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=99900, currency="INR",
        key_id="rzp_test_key")))

    client.http.post(f"{BASE}/checkout", json={"tier": "pro"})

    service = app.dependency_overrides[get_payment_service]()
    assert service.calls[0] == (7, "pro", None)


def test_checkout_returns_the_discount_breakdown_when_there_is_one(client):
    """amount_paise stays what Razorpay will charge, so a client ignoring the
    three new fields still charges the right number."""
    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=49900, currency="INR",
        key_id="rzp_test_key", list_amount_paise=99900, discount_paise=50000,
        coupon_code="FOUNDER100")))

    body = client.http.post(f"{BASE}/checkout",
                            json={"tier": "pro", "coupon_code": "founder100"}).json()

    assert body["amount_paise"] == 49900
    assert body["list_amount_paise"] == 99900
    assert body["discount_paise"] == 50000
    assert body["coupon_code"] == "FOUNDER100"


# --- confirm ----------------------------------------------------------------
#
# The route that lets a founder stop waiting on the webhook. Whether a
# confirmation is genuine is PaymentService's question (and
# test_payments_service.py's); what matters here is that the route hands it the
# founder's OWN id, never one from the body, and translates the service's
# outcome honestly.

def test_confirm_requires_authentication():
    bare = TestClient(app)
    r = bare.post(f"{BASE}/confirm",
                  json={"order_id": "order_1", "razorpay_payment_id": "pay_1"})
    assert r.status_code != 200


def test_confirm_passes_the_authenticated_founders_own_id(client):
    """The body carries only what Razorpay's widget handed the browser. A
    founder_id from the body would be a founder choosing whose plan to upgrade."""
    service = FakeService(confirm_result=WebhookResult(
        outcome=WebhookOutcome.CAPTURED, payment_id=1, founder_id=7, plan="pro"))
    _use(service)

    r = client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_1", "razorpay_payment_id": "pay_1",
        "razorpay_signature": "sig"})

    assert r.status_code == 200
    assert service.confirm_calls == [(7, "order_1", "pay_1", "sig")]


def test_confirm_reports_a_granted_plan_as_activated(client):
    _use(FakeService(confirm_result=WebhookResult(
        outcome=WebhookOutcome.CAPTURED, payment_id=1, founder_id=7, plan="pro")))

    body = client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_1", "razorpay_payment_id": "pay_1"}).json()

    assert body == {"activated": True, "outcome": "captured", "plan": "pro"}


def test_confirm_reports_a_webhook_that_already_granted_as_activated(client):
    """The founder is on the plan either way -- which of the two paths got
    there first is not something the UI should have to care about."""
    _use(FakeService(confirm_result=WebhookResult(
        outcome=WebhookOutcome.ALREADY_PROCESSED, payment_id=1, founder_id=7)))

    body = client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_1", "razorpay_payment_id": "pay_1"}).json()

    assert body["activated"] is True


def test_confirm_does_not_claim_activation_for_an_uncaptured_payment(client):
    _use(FakeService(confirm_result=WebhookResult(
        outcome=WebhookOutcome.NOT_CAPTURED, payment_id=1, founder_id=7)))

    body = client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_1", "razorpay_payment_id": "pay_1"}).json()

    assert body == {"activated": False, "outcome": "not_captured", "plan": None}


def test_confirm_reports_someone_elses_order_as_404(client):
    _use(FakeService(raises=PaymentNotFoundError()))
    r = client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_not_mine", "razorpay_payment_id": "pay_1"})
    assert r.status_code == 404


def test_confirm_rejects_extra_fields(client):
    """Notably a tier or an amount: nothing the browser sends may influence
    what this grants."""
    _use(FakeService())
    r = client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_1", "razorpay_payment_id": "pay_1", "tier": "pro"})
    assert r.status_code == 422


def test_confirm_elevates_the_rls_context_for_the_grant(client):
    """Granting writes subscription and founder rows a founder's own RLS
    context cannot -- the same elevation the webhook route makes, and the
    reason the service checks ownership itself."""
    sessions = []

    def _session():
        s = FakeSession()
        sessions.append(s)
        return s

    app.dependency_overrides[get_db] = _session
    _use(FakeService(confirm_result=WebhookResult(
        outcome=WebhookOutcome.CAPTURED, payment_id=1, founder_id=7, plan="pro")))

    client.http.post(f"{BASE}/confirm", json={
        "order_id": "order_1", "razorpay_payment_id": "pay_1"})

    assert any(s.info for s in sessions), "confirm ran without an admin RLS context"


def test_checkout_forwards_the_buyers_state_as_the_place_of_supply(client):
    """The one fact only the founder knows. It says WHERE the supply went; the
    backend decides what that costs in tax."""
    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=99900, currency="INR",
        key_id="rzp_test_key")))

    client.http.post(f"{BASE}/checkout", json={"tier": "pro", "billing_state": "Gujarat"})

    service = app.dependency_overrides[get_payment_service]()
    assert service.state_calls[0] == "Gujarat"


def test_checkout_still_works_without_a_state(client):
    """Optional at the API so an older frontend keeps working: the payment
    succeeds and the invoice simply claims no place of supply."""
    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=99900, currency="INR",
        key_id="rzp_test_key")))

    resp = client.http.post(f"{BASE}/checkout", json={"tier": "pro"})

    assert resp.status_code == 200
    service = app.dependency_overrides[get_payment_service]()
    assert service.state_calls[0] is None


def test_the_states_endpoint_serves_the_list_the_tax_decision_uses(client):
    """One list, so the dropdown and the CGST/SGST-vs-IGST comparison cannot
    disagree about how a state is spelt."""
    resp = client.http.get(f"{BASE}/states")

    assert resp.status_code == 200
    states = resp.json()
    by_name = {s["name"]: s["code"] for s in states}
    assert by_name["Gujarat"] == "24"      # the supplier's own state
    assert by_name["Karnataka"] == "29"
    assert len(states) > 30


# --- personal vs business at the checkout route ----------------------------

def test_a_business_checkout_forwards_the_buyers_tax_identity(client):
    from app.payments.models import PurchaseType

    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=99900, currency="INR",
        key_id="rzp_test_key")))

    client.http.post(f"{BASE}/checkout", json={
        "tier": "pro", "billing_state": "Gujarat", "purchase_type": "business",
        "business_gstin": "24AALCG5562B1ZS", "business_name": "Blissnack Pvt Ltd",
        "business_address": "402, Race Course Road, Vadodara",
    })

    service = app.dependency_overrides[get_payment_service]()
    purchase_type, business = service.buyer_calls[0]
    assert purchase_type == PurchaseType.BUSINESS
    assert business.gstin == "24AALCG5562B1ZS"
    assert business.legal_name == "Blissnack Pvt Ltd"
    assert business.address == "402, Race Course Road, Vadodara"


def test_a_personal_checkout_carries_no_business_object_at_all(client):
    """The service is never handed half a business on a personal checkout."""
    from app.payments.models import PurchaseType

    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=99900, currency="INR",
        key_id="rzp_test_key")))

    client.http.post(f"{BASE}/checkout",
                     json={"tier": "pro", "purchase_type": "personal"})

    service = app.dependency_overrides[get_payment_service]()
    purchase_type, business = service.buyer_calls[0]
    assert purchase_type == PurchaseType.PERSONAL
    assert business is None


def test_an_older_client_that_sends_no_purchase_type_still_checks_out(client):
    """A payment with no purchase type records none and renders the personal
    layout -- which is what those founders were already getting."""
    _use(FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_1", amount_paise=99900, currency="INR",
        key_id="rzp_test_key")))

    resp = client.http.post(f"{BASE}/checkout", json={"tier": "pro"})

    assert resp.status_code == 200
    service = app.dependency_overrides[get_payment_service]()
    assert service.buyer_calls[0] == (None, None)


def test_an_unknown_purchase_type_is_rejected(client):
    _use(FakeService())
    r = client.http.post(f"{BASE}/checkout",
                         json={"tier": "pro", "purchase_type": "charity"})
    assert r.status_code == 422


def test_bad_business_details_are_refused_with_the_reason(client):
    """422 and the service's own sentence, because it names the specific thing
    to fix and the founder is at the keyboard to fix it."""
    from app.payments.errors import InvalidBusinessDetailsError

    _use(FakeService(raises=InvalidBusinessDetailsError(
        "Your GSTIN is registered in Maharashtra, but you selected Gujarat.")))

    r = client.http.post(f"{BASE}/checkout", json={
        "tier": "pro", "billing_state": "Gujarat", "purchase_type": "business",
        "business_gstin": "27AALCG5562B1ZS", "business_name": "X Pvt Ltd",
    })

    assert r.status_code == 422
    assert "Maharashtra" in r.json()["message"]
