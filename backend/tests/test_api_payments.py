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
from app.main import app
from app.payments.errors import (
    InvalidCheckoutError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
)
from app.payments.models import CheckoutSession

BASE = "/api/v1/payments"


class FakeService:
    def __init__(self, *, session=None, raises=None):
        self.session = session
        self.raises = raises
        self.calls = []

    def start_checkout(self, founder_id, tier, coupon_code=None):
        self.calls.append((founder_id, tier, coupon_code))
        if self.raises:
            raise self.raises
        return self.session


@pytest.fixture
def client():
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(founder_id=7)
    yield SimpleNamespace(http=TestClient(app))
    app.dependency_overrides.pop(get_founder_record, None)
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
