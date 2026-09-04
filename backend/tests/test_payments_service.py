"""PaymentService -- the money-safety core of Phase 4.

Every fake below is a plain hand-written double, not the real gateway/DB --
this is what lets these tests assert on the actual safety properties (never
grant twice, never grant from an unsigned payload, never fake a checkout
when unconfigured) without a live Razorpay account or a database.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from app.credits.models import CreditOperation
from app.payments.errors import (
    InvalidCheckoutError,
    InvalidWebhookSignatureError,
    PaymentsNotConfiguredError,
)
from app.payments.gateway import GatewayOrder
from app.payments.models import WebhookOutcome
from app.payments.service import PaymentService
from app.plans.catalog import PlanTier

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
WEBHOOK_SECRET = "whsec_test"


# --- fakes ---------------------------------------------------------------

class FakeGateway:
    def __init__(self, *, order_id="order_1", raise_on_create=None):
        self.key_id = "rzp_test_key"
        self.order_id = order_id
        self.raise_on_create = raise_on_create
        self.created_orders = []

    def create_order(self, *, amount_paise, currency, receipt, notes):
        if self.raise_on_create:
            raise self.raise_on_create
        self.created_orders.append(
            {"amount_paise": amount_paise, "currency": currency, "receipt": receipt, "notes": notes})
        return GatewayOrder(order_id=self.order_id, amount_paise=amount_paise, currency=currency)

    def verify_payment_signature(self, *, order_id, payment_id, signature):
        return True

    def verify_webhook_signature(self, *, body, signature):
        expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")


class FakeRepository:
    def __init__(self):
        self._payments: dict[int, dict] = {}
        self._by_order: dict[str, int] = {}
        self._by_gpid: dict[str, int] = {}
        self._next_payment_id = 1
        self._next_subscription_id = 1
        self.subscriptions_created = []
        self.plans_granted = []

    def create_pending(self, *, founder_id, amount_inr, currency, gateway, gateway_order_id):
        pid = self._next_payment_id
        self._next_payment_id += 1
        self._payments[pid] = {
            "payment_id": pid, "founder_id": founder_id, "status": "pending",
            "gateway_order_id": gateway_order_id, "gateway_payment_id": None,
            "amount_inr": amount_inr, "subscription_id": None,
        }
        self._by_order[gateway_order_id] = pid
        return pid

    def get_by_gateway_order_id(self, gateway_order_id):
        pid = self._by_order.get(gateway_order_id)
        return self._record(pid) if pid else None

    def get_by_gateway_payment_id(self, gateway_payment_id):
        pid = self._by_gpid.get(gateway_payment_id)
        return self._record(pid) if pid else None

    def mark_captured(self, payment_id, *, gateway_payment_id, paid_at, subscription_id):
        row = self._payments[payment_id]
        row["status"] = "success"
        row["gateway_payment_id"] = gateway_payment_id
        row["subscription_id"] = subscription_id
        self._by_gpid[gateway_payment_id] = payment_id

    def mark_failed(self, payment_id, *, reason):
        self._payments[payment_id]["status"] = "failed"
        self._payments[payment_id]["failure_reason"] = reason

    def create_subscription(self, *, founder_id, plan_type, amount_inr, billing_cycle,
                            expires_at, gateway):
        sid = self._next_subscription_id
        self._next_subscription_id += 1
        self.subscriptions_created.append(
            {"subscription_id": sid, "founder_id": founder_id, "plan_type": plan_type,
             "amount_inr": amount_inr, "billing_cycle": billing_cycle, "expires_at": expires_at,
             "gateway": gateway})
        return sid

    def grant_plan(self, founder_id, plan_type):
        self.plans_granted.append((founder_id, plan_type))

    def _record(self, pid):
        from app.payments.models import PaymentRecord
        if pid is None:
            return None
        row = self._payments[pid]
        return PaymentRecord(payment_id=row["payment_id"], founder_id=row["founder_id"],
                             status=row["status"], gateway_order_id=row["gateway_order_id"],
                             gateway_payment_id=row["gateway_payment_id"],
                             amount_inr=row["amount_inr"], subscription_id=row["subscription_id"])


class FakeCredits:
    def __init__(self, *, raise_on_adjust=None):
        self.grants = []
        self.raise_on_adjust = raise_on_adjust

    def adjust(self, founder_id, *, admin_id, operation, amount, reason):
        if self.raise_on_adjust:
            raise self.raise_on_adjust
        self.grants.append({"founder_id": founder_id, "admin_id": admin_id,
                            "operation": operation, "amount": amount, "reason": reason})


_UNSET = object()


def _service(*, gateway=_UNSET, repository=None, credits=None) -> tuple[PaymentService, FakeRepository, FakeCredits]:
    repo = repository or FakeRepository()
    cred = credits or FakeCredits()
    gw = FakeGateway() if gateway is _UNSET else gateway
    return PaymentService(gw, repo, cred, clock=lambda: NOW), repo, cred


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _captured_event(*, order_id="order_1", payment_id="pay_1", tier="starter") -> bytes:
    return json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": payment_id, "order_id": order_id,
            "notes": {"founder_id": "42", "plan_tier": tier},
        }}},
    }).encode()


def _failed_event(*, order_id="order_1", reason="card declined") -> bytes:
    return json.dumps({
        "event": "payment.failed",
        "payload": {"payment": {"entity": {"order_id": order_id, "error_description": reason}}},
    }).encode()


# --- start_checkout --------------------------------------------------------

def test_checkout_unconfigured_gateway_refuses():
    service, _, _ = _service(gateway=None)
    with pytest.raises(PaymentsNotConfiguredError):
        service.start_checkout(1, PlanTier.STARTER)


def test_checkout_refuses_the_free_plan():
    service, _, _ = _service()
    with pytest.raises(InvalidCheckoutError):
        service.start_checkout(1, PlanTier.FREE)


def test_checkout_creates_a_pending_payment_and_a_real_order():
    service, repo, _ = _service()
    session = service.start_checkout(42, PlanTier.STARTER)

    assert session.order_id == "order_1"
    assert session.amount_paise == 45000        # Rs 450 * 100
    assert session.currency == "INR"
    assert session.key_id == "rzp_test_key"

    payment = repo.get_by_gateway_order_id("order_1")
    assert payment.founder_id == 42
    assert payment.status == "pending"
    assert payment.amount_inr == 450


def test_checkout_carries_founder_and_plan_in_the_order_notes():
    """This is how the webhook later learns which plan to grant -- payments
    has no plan_type column, see app/payments/service.py's own note."""
    gateway = FakeGateway()
    service, _, _ = _service(gateway=gateway)
    service.start_checkout(42, PlanTier.PRO)
    assert gateway.created_orders[0]["notes"] == {"founder_id": "42", "plan_tier": "pro"}


# --- handle_webhook: signature / configuration -----------------------------

def test_webhook_unconfigured_gateway_refuses():
    service, _, _ = _service(gateway=None)
    with pytest.raises(PaymentsNotConfiguredError):
        service.handle_webhook(body=b"{}", signature="whatever")


def test_webhook_bad_signature_is_rejected():
    service, _, _ = _service()
    with pytest.raises(InvalidWebhookSignatureError):
        service.handle_webhook(body=_captured_event(), signature="0" * 64)


def test_webhook_missing_signature_is_rejected():
    service, _, _ = _service()
    with pytest.raises(InvalidWebhookSignatureError):
        service.handle_webhook(body=_captured_event(), signature="")


# --- handle_webhook: payment.captured ---------------------------------------

def test_captured_payment_grants_the_plan_and_credits():
    service, repo, credits = _service()
    service.start_checkout(42, PlanTier.STARTER)   # creates the pending payment for order_1

    body = _captured_event(order_id="order_1", payment_id="pay_1", tier="starter")
    result = service.handle_webhook(body=body, signature=_sign(body))

    assert result.outcome == WebhookOutcome.CAPTURED
    assert result.founder_id == 42
    assert result.plan == "starter"

    assert repo.plans_granted == [(42, "starter")]
    assert len(repo.subscriptions_created) == 1
    assert repo.subscriptions_created[0]["plan_type"] == "starter"
    assert credits.grants[0]["founder_id"] == 42
    assert credits.grants[0]["operation"] == CreditOperation.ADD
    assert credits.grants[0]["amount"] == 180   # Starter's monthly_credits


def test_captured_payment_is_idempotent_on_retry():
    """Razorpay retries webhook deliveries -- the same payment must never
    grant a plan or credits twice."""
    service, repo, credits = _service()
    service.start_checkout(42, PlanTier.STARTER)
    body = _captured_event(order_id="order_1", payment_id="pay_1", tier="starter")

    first = service.handle_webhook(body=body, signature=_sign(body))
    second = service.handle_webhook(body=body, signature=_sign(body))

    assert first.outcome == WebhookOutcome.CAPTURED
    assert second.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.plans_granted == [(42, "starter")]      # only once
    assert len(credits.grants) == 1                      # only once


def test_captured_payment_for_an_unknown_order_is_not_granted():
    """A captured event for an order this backend never created -- never
    silently grant a plan to nobody in particular."""
    service, repo, credits = _service()
    body = _captured_event(order_id="order_never_created", payment_id="pay_1")
    result = service.handle_webhook(body=body, signature=_sign(body))

    assert result.outcome == WebhookOutcome.UNKNOWN_PAYMENT
    assert repo.plans_granted == []
    assert credits.grants == []


def test_captured_payment_with_no_recognisable_plan_tier_note_is_not_granted():
    service, repo, _ = _service()
    service.start_checkout(42, PlanTier.STARTER)
    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_1", "order_id": "order_1", "notes": {},
        }}},
    }).encode()

    result = service.handle_webhook(body=body, signature=_sign(body))
    assert result.outcome == WebhookOutcome.UNKNOWN_PAYMENT
    assert repo.plans_granted == []


def test_a_credit_grant_failure_does_not_undo_the_plan_grant():
    """The plan is the thing that matters most and is already committed by
    the time credits are attempted -- a credit-service hiccup must not roll
    it back or crash the whole webhook."""
    service, repo, _ = _service(credits=FakeCredits(raise_on_adjust=RuntimeError("ledger down")))
    service.start_checkout(42, PlanTier.STARTER)
    body = _captured_event(order_id="order_1", payment_id="pay_1", tier="starter")

    result = service.handle_webhook(body=body, signature=_sign(body))

    assert result.outcome == WebhookOutcome.CAPTURED
    assert repo.plans_granted == [(42, "starter")]


# --- handle_webhook: payment.failed -----------------------------------------

def test_failed_payment_is_recorded_without_granting_anything():
    service, repo, credits = _service()
    service.start_checkout(42, PlanTier.STARTER)
    body = _failed_event(order_id="order_1")

    result = service.handle_webhook(body=body, signature=_sign(body))

    assert result.outcome == WebhookOutcome.FAILED_RECORDED
    payment = repo.get_by_gateway_order_id("order_1")
    assert payment.status == "failed"
    assert repo.plans_granted == []
    assert credits.grants == []


# --- handle_webhook: anything else ------------------------------------------

def test_unhandled_event_types_are_ignored_not_errored():
    service, _, _ = _service()
    body = json.dumps({"event": "refund.processed", "payload": {}}).encode()
    result = service.handle_webhook(body=body, signature=_sign(body))
    assert result.outcome == WebhookOutcome.IGNORED_EVENT
