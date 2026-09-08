"""API tests for the founder's billing surface.

    POST /payments/subscription          start a Plus/Pro mandate
    GET  /payments/subscription          current subscription + entitlement
    POST /payments/subscription/cancel   cancel
    GET  /payments/invoices              receipts
    GET  /payments/history               every payment, failures included
    GET/PUT /payments/billing-profile    name / GSTIN / address

Same shape as test_api_payments.py: dependency_overrides inject a fake founder
and fake services, so no database and no Razorpay account. The behaviour these
prove is ROUTING -- that the founder's own id is what reaches the service, that
errors map to the right status, and that the response says what the page needs.
The money-safety logic itself lives in test_payments_subscriptions.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_founder_record
from app.api.v1.payments.billing_router import (
    get_billing_profile_service,
    get_subscription_repository,
    get_subscription_service,
)
from app.db.session import get_db
from app.main import app
from app.payments.billing_profile import BillingProfile
from app.payments.errors import (
    InvalidBillingProfileError,
    NoActiveSubscriptionError,
    SubscriptionAlreadyActiveError,
    SubscriptionPlanNotConfiguredError,
)
from app.payments.subscription_repository import SubscriptionRecord
from app.payments.subscriptions import CancellationResult, SubscriptionCheckoutSession

BASE = "/api/v1/payments"
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
PERIOD_END = NOW + timedelta(days=30)


class FakeSession:
    """Enough Session for `set_admin_rls_context` on the cancel route."""

    def __init__(self):
        self.info = {}

    def in_transaction(self):
        return False


def _record(**overrides) -> SubscriptionRecord:
    base = dict(
        subscription_id=1, founder_id=7, plan_type="starter", status="active",
        gateway_subscription_id="sub_1", razorpay_plan_id="plan_PLUS", amount_inr=499,
        paid_count=1, current_period_start=NOW, current_period_end=PERIOD_END,
        next_charge_at=PERIOD_END, access_until=PERIOD_END + timedelta(days=5),
        cancel_at_period_end=False, cancelled_at=None, ended_at=None,
        activated_at=NOW, started_at=NOW, billing_cycle="monthly",
    )
    base.update(overrides)
    return SubscriptionRecord(**base)


class FakeSubscriptionService:
    def __init__(self, *, current=None, session=None, cancel_result=None, raises=None):
        self._current = current
        self._session = session
        self._cancel_result = cancel_result
        self.raises = raises
        self.start_calls = []
        self.cancel_calls = []

    def start_subscription(self, founder_id, tier):
        self.start_calls.append((founder_id, tier))
        if self.raises:
            raise self.raises
        return self._session

    def cancel(self, founder_id, *, at_period_end=True, reason=None):
        self.cancel_calls.append((founder_id, at_period_end, reason))
        if self.raises:
            raise self.raises
        return self._cancel_result

    def current(self, founder_id):
        return self._current


class FakeRepository:
    def __init__(self, invoices=None, payments=None):
        self._invoices = invoices or []
        self._payments = payments or []
        self.invoice_calls = []
        self.payment_calls = []

    def list_invoices(self, founder_id, *, limit=50):
        self.invoice_calls.append((founder_id, limit))
        return self._invoices

    def list_payments(self, founder_id, *, limit=50):
        self.payment_calls.append((founder_id, limit))
        return self._payments


class FakeProfileService:
    def __init__(self, profile=None, raises=None):
        self.profile = profile
        self.raises = raises
        self.saved = []

    def get(self, founder_id):
        return self.profile

    def save(self, founder_id, **fields):
        self.saved.append((founder_id, fields))
        if self.raises:
            raise self.raises
        self.profile = BillingProfile(
            founder_id=founder_id, customer_type=fields["customer_type"],
            business_name=fields.get("business_name"), gstin=fields.get("gstin"),
            billing_address=fields.get("billing_address"),
            billing_city=fields.get("billing_city"),
            billing_state=fields.get("billing_state"),
            billing_pincode=fields.get("billing_pincode"),
            billing_country=fields.get("billing_country") or "IN")
        return self.profile


@pytest.fixture
def client():
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=7, plan_type="starter")
    app.dependency_overrides[get_db] = lambda: FakeSession()
    yield SimpleNamespace(http=TestClient(app))
    for dep in (get_founder_record, get_db, get_subscription_service,
                get_subscription_repository, get_billing_profile_service):
        app.dependency_overrides.pop(dep, None)


def _use_subscriptions(service):
    app.dependency_overrides[get_subscription_service] = lambda: service


def _use_repository(repo):
    app.dependency_overrides[get_subscription_repository] = lambda: repo


def _use_profile(service):
    app.dependency_overrides[get_billing_profile_service] = lambda: service


# --- POST /payments/subscription --------------------------------------------

def test_subscribe_requires_authentication():
    """No get_founder_record override installed -- the real dependency chain
    runs and refuses.

    `raise_server_exceptions=False` so the assertion is about the RESPONSE
    rather than about which exception happens to escape. Without it this test
    passes only where a migrated database exists to reject the caller
    politely, and errors out everywhere else -- for a reason that has nothing
    to do with authentication.
    """
    bare = TestClient(app, raise_server_exceptions=False)
    assert bare.post(f"{BASE}/subscription", json={"tier": "starter"}).status_code != 200


def test_subscribe_passes_the_authenticated_founders_own_id(client):
    """The founder id comes from the TOKEN, never from the body -- otherwise a
    founder could start a subscription in someone else's name."""
    service = FakeSubscriptionService(session=SubscriptionCheckoutSession(
        subscription_id=1, gateway_subscription_id="sub_1", razorpay_plan_id="plan_PLUS",
        key_id="rzp_test_k", tier="starter", plan_name="Plus", amount_inr=499))
    _use_subscriptions(service)

    r = client.http.post(f"{BASE}/subscription", json={"tier": "starter"})

    assert r.status_code == 200
    assert service.start_calls[0][0] == 7
    body = r.json()
    assert body["razorpay_subscription_id"] == "sub_1"
    assert body["key_id"] == "rzp_test_k"
    assert body["amount_inr"] == 499


def test_subscribe_rejects_an_unknown_tier(client):
    _use_subscriptions(FakeSubscriptionService())
    assert client.http.post(f"{BASE}/subscription",
                            json={"tier": "platinum"}).status_code == 422


def test_subscribe_rejects_extra_fields(client):
    """`extra='forbid'`. A body carrying `amount` or `razorpay_plan_id` must be
    refused rather than silently ignored -- silently ignoring it is how a
    client comes to believe it is setting the price."""
    _use_subscriptions(FakeSubscriptionService())
    r = client.http.post(f"{BASE}/subscription",
                         json={"tier": "starter", "amount_inr": 1})
    assert r.status_code == 422


def test_subscribe_reports_an_unregistered_plan_as_503(client):
    _use_subscriptions(FakeSubscriptionService(
        raises=SubscriptionPlanNotConfiguredError(plan_name="Plus")))
    assert client.http.post(f"{BASE}/subscription",
                            json={"tier": "starter"}).status_code == 503


def test_subscribe_reports_an_existing_subscription_as_409(client):
    """Refused, not stacked: two mandates means two charges a month."""
    _use_subscriptions(FakeSubscriptionService(
        raises=SubscriptionAlreadyActiveError(plan_name="Plus", access_until=PERIOD_END)))
    r = client.http.post(f"{BASE}/subscription", json={"tier": "starter"})
    assert r.status_code == 409
    assert "Plus" in r.json()["message"]


# --- GET /payments/subscription ---------------------------------------------

def test_subscription_reports_the_entitlement_alongside_the_status(client):
    """The page branches on `entitlement`, not on `status`. Reported by the
    server rather than derived client-side because the two differ exactly where
    it matters most."""
    _use_subscriptions(FakeSubscriptionService(current=_record()))

    body = client.http.get(f"{BASE}/subscription").json()

    assert body["has_subscription"] is True
    assert body["is_recurring"] is True
    assert body["plan_name"] == "Plus"
    assert body["next_charge_at"].startswith("2026-10-08")
    assert body["entitlement"]["is_paid"] is True
    assert body["entitlement"]["access_until"].startswith("2026-10-13")


def test_a_cancelled_subscription_is_still_reported_as_entitled(client):
    """The founder paid for the rest of the month. A client that read
    "cancelled" as "gone" would tell them they had lost something they still
    have -- on the page where they would go looking for a refund."""
    _use_subscriptions(FakeSubscriptionService(current=_record(
        status="cancelled", cancel_at_period_end=True, cancelled_at=NOW,
        access_until=PERIOD_END)))

    body = client.http.get(f"{BASE}/subscription").json()

    assert body["status"] == "cancelled"
    assert body["cancel_at_period_end"] is True
    assert body["entitlement"]["is_paid"] is True
    assert body["entitlement"]["access_until"].startswith("2026-10-08")


def test_no_subscription_is_a_normal_answer_not_an_error(client):
    """A founder on Free, or one who bought the one-time Starter. A 404 here
    would make the client branch on an error to render an ordinary page."""
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=7, plan_type="free")
    _use_subscriptions(FakeSubscriptionService(current=None))

    body = client.http.get(f"{BASE}/subscription").json()

    assert body["has_subscription"] is False
    assert body["entitlement"]["plan"] == "free"
    assert body["entitlement"]["is_paid"] is False


def test_the_entitlement_follows_the_founder_row_not_the_subscription(client):
    """`founders.plan_type` is the one source of truth every feature gate
    reads. Where the two disagree the subscription row is a billing record and
    the founder column is the access -- reporting the billing record would tell
    a founder whose charge failed that they still have Pro."""
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=7, plan_type="free")
    _use_subscriptions(FakeSubscriptionService(current=_record(plan_type="pro")))

    body = client.http.get(f"{BASE}/subscription").json()

    assert body["tier"] == "pro"                  # what they were billed for
    assert body["entitlement"]["plan"] == "free"  # what they can actually use
    assert body["entitlement"]["is_paid"] is False


# --- POST /payments/subscription/cancel -------------------------------------

def test_cancel_defaults_to_period_end(client):
    service = FakeSubscriptionService(cancel_result=CancellationResult(
        subscription_id=1, status="active", cancel_at_period_end=True,
        access_until=PERIOD_END))
    _use_subscriptions(service)

    r = client.http.post(f"{BASE}/subscription/cancel", json={})

    assert r.status_code == 200
    assert service.cancel_calls == [(7, True, None)]
    # The date is in the message the founder reads, not only in a field they
    # might not render.
    assert "08 October 2026" in r.json()["message"]
    assert r.json()["access_until"].startswith("2026-10-08")


def test_cancel_forwards_the_reason(client):
    service = FakeSubscriptionService(cancel_result=CancellationResult(
        subscription_id=1, status="active", cancel_at_period_end=True,
        access_until=PERIOD_END))
    _use_subscriptions(service)

    client.http.post(f"{BASE}/subscription/cancel",
                     json={"at_period_end": True, "reason": "too expensive"})

    assert service.cancel_calls[0][2] == "too expensive"


def test_cancel_with_nothing_to_cancel_is_a_404(client):
    _use_subscriptions(FakeSubscriptionService(raises=NoActiveSubscriptionError()))
    assert client.http.post(f"{BASE}/subscription/cancel", json={}).status_code == 404


def test_cancel_elevates_the_rls_context(client):
    """Same elevation POST /payments/confirm takes: a cancellation writes the
    subscriptions row a SYSTEM actor owns, and the founder-isolation policies
    do not let a founder's own context write it on their behalf."""
    session = FakeSession()
    app.dependency_overrides[get_db] = lambda: session
    _use_subscriptions(FakeSubscriptionService(cancel_result=CancellationResult(
        subscription_id=1, status="cancelled", cancel_at_period_end=False,
        access_until=NOW)))

    client.http.post(f"{BASE}/subscription/cancel", json={})

    assert session.info.get("admin_rls") or session.info


def test_cancel_rejects_extra_fields(client):
    _use_subscriptions(FakeSubscriptionService())
    assert client.http.post(f"{BASE}/subscription/cancel",
                            json={"at_period_end": True, "force": True}).status_code == 422


# --- receipts ---------------------------------------------------------------

def test_invoices_are_scoped_to_the_authenticated_founder(client):
    repo = FakeRepository(invoices=[{
        "invoice_id": 1, "gateway_invoice_id": "inv_1", "invoice_number": "INV-001",
        "amount_inr": 499, "tax_amount_inr": None, "total_amount_inr": 499,
        "currency": "INR", "status": "paid", "invoice_url": "https://rzp.io/i/a",
        "issued_at": NOW, "paid_at": NOW, "due_at": None}])
    _use_repository(repo)

    body = client.http.get(f"{BASE}/invoices").json()

    assert repo.invoice_calls[0][0] == 7
    assert body[0]["invoice_number"] == "INV-001"
    assert body[0]["invoice_url"] == "https://rzp.io/i/a"
    # No tax number is invented where Razorpay reported none.
    assert body[0]["tax_amount_inr"] is None


def test_payment_history_includes_failures_and_their_reason(client):
    """Shown rather than filtered out: a founder whose renewal did not go
    through needs to see that, with the reason, on the page where they would
    fix it."""
    repo = FakeRepository(payments=[{
        "payment_id": 2, "amount_inr": 499, "currency": "INR", "status": "failed",
        "gateway_payment_id": None, "gateway_order_id": None,
        "gateway_subscription_id": "sub_1", "gateway_invoice_id": None,
        "plan_tier": "starter", "failure_reason": "insufficient funds",
        "paid_at": None, "refunded_at": None, "created_at": NOW}])
    _use_repository(repo)

    body = client.http.get(f"{BASE}/history").json()

    assert repo.payment_calls[0][0] == 7
    assert body[0]["status"] == "failed"
    assert body[0]["failure_reason"] == "insufficient funds"
    # The founder-facing name, not the internal tier id -- 'starter' is Plus.
    assert body[0]["plan_name"] == "Plus"


# --- billing profile ---------------------------------------------------------

def test_an_absent_billing_profile_is_an_empty_one_not_a_404(client):
    """"You have not filled this in" is the normal state for most founders."""
    _use_profile(FakeProfileService(profile=None))

    body = client.http.get(f"{BASE}/billing-profile").json()

    assert body["customer_type"] == "individual"
    assert body["is_invoice_ready"] is False


def test_saving_a_billing_profile_returns_it(client):
    service = FakeProfileService()
    _use_profile(service)

    r = client.http.put(f"{BASE}/billing-profile", json={
        "customer_type": "business", "business_name": "GoXL Labs",
        "gstin": "29ABCDE1234F1Z5", "billing_address": "1 Road",
        "billing_state": "Karnataka", "billing_pincode": "560001"})

    assert r.status_code == 200
    assert service.saved[0][0] == 7
    assert r.json()["business_name"] == "GoXL Labs"
    assert r.json()["is_invoice_ready"] is True


def test_a_bad_gstin_is_a_422_whose_message_names_the_problem(client):
    """Shown to the founder verbatim: replacing it with a generic "invalid"
    leaves them guessing at a 15-character string."""
    _use_profile(FakeProfileService(raises=InvalidBillingProfileError(
        "that GSTIN is not a valid 15-character GST number")))

    r = client.http.put(f"{BASE}/billing-profile", json={
        "customer_type": "business", "business_name": "GoXL", "gstin": "NOPE"})

    assert r.status_code == 422
    assert "GST" in r.json()["message"]


def test_billing_profile_rejects_an_unknown_customer_type(client):
    _use_profile(FakeProfileService())
    assert client.http.put(f"{BASE}/billing-profile",
                           json={"customer_type": "enterprise"}).status_code == 422


def test_billing_profile_requires_authentication():
    bare = TestClient(app, raise_server_exceptions=False)
    assert bare.get(f"{BASE}/billing-profile").status_code != 200
