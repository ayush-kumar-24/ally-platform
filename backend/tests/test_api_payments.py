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
from app.api.v1.payments.router import get_payment_service
from app.main import app
from app.payments.errors import InvalidCheckoutError, PaymentsNotConfiguredError
from app.payments.models import CheckoutSession

BASE = "/api/v1/payments"


class FakeService:
    def __init__(self, *, session=None, raises=None):
        self.session = session
        self.raises = raises
        self.calls = []

    def start_checkout(self, founder_id, tier):
        self.calls.append((founder_id, tier))
        if self.raises:
            raise self.raises
        return self.session


@pytest.fixture
def client():
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(founder_id=7)
    yield SimpleNamespace(http=TestClient(app))
    app.dependency_overrides.pop(get_founder_record, None)
    app.dependency_overrides.pop(get_payment_service, None)


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
    assert service.calls == [(7, "starter")]


def test_checkout_returns_the_session_the_frontend_needs(client):
    service = FakeService(session=CheckoutSession(
        payment_id=1, order_id="order_abc", amount_paise=99900, currency="INR",
        key_id="rzp_live_key"))
    _use(service)

    body = client.http.post(f"{BASE}/checkout", json={"tier": "pro"}).json()
    assert body == {"payment_id": 1, "order_id": "order_abc", "amount_paise": 99900,
                    "currency": "INR", "key_id": "rzp_live_key"}


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


def test_checkout_reports_422_for_the_free_plan(client):
    _use(FakeService(raises=InvalidCheckoutError("the free plan needs no checkout")))
    r = client.http.post(f"{BASE}/checkout", json={"tier": "free"})
    assert r.status_code == 422
