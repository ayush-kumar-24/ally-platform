"""API tests for POST /webhooks/razorpay.

`container.payment_service` is monkeypatched rather than using
app.dependency_overrides -- this router calls `container.payment_service(db)`
directly (same shape as internal_jobs.py's `/check-health`), not through a
FastAPI Depends() seam, so there is no dependency to override.

The webhook_logs writes go through the real (unreachable, in this sandbox)
`get_db` -- caught and logged rather than raised (see razorpay.py's own
_log_webhook/_mark_processed), so these tests prove the response the caller
actually gets is correct regardless of whether that logging succeeded.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.container import container
from app.main import app
from app.payments.errors import InvalidWebhookSignatureError, PaymentsNotConfiguredError
from app.payments.models import WebhookOutcome, WebhookResult

BASE = "/api/v1/webhooks/razorpay"


class FakeService:
    def __init__(self, *, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.calls = []

    def handle_webhook(self, *, body, signature):
        self.calls.append((body, signature))
        if self.raises:
            raise self.raises
        return self.result


@pytest.fixture
def client():
    return TestClient(app)


def _use(monkeypatch, service: FakeService) -> None:
    monkeypatch.setattr(container, "payment_service", lambda db: service)


def _captured_body() -> bytes:
    return json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_1", "notes": {}}}},
    }).encode()


def test_captured_event_is_forwarded_to_the_service(client, monkeypatch):
    service = FakeService(result=WebhookResult(outcome=WebhookOutcome.CAPTURED, payment_id=1,
                                               founder_id=42, plan="starter"))
    _use(monkeypatch, service)

    body = _captured_body()
    r = client.post(BASE, content=body, headers={"X-Razorpay-Signature": "sig_abc"})

    assert r.status_code == 200
    assert r.json() == {"outcome": "captured", "payment_id": 1}
    assert service.calls == [(body, "sig_abc")]


def test_missing_signature_header_is_passed_through_as_empty_string(client, monkeypatch):
    """The route must not treat a missing header as "skip verification" --
    it hands an empty string to the service, which fails closed on it (see
    test_payments_service.py's own coverage of that)."""
    service = FakeService(raises=InvalidWebhookSignatureError())
    _use(monkeypatch, service)

    client.post(BASE, content=_captured_body())
    assert service.calls[0][1] == ""


def test_bad_signature_returns_401(client, monkeypatch):
    _use(monkeypatch, FakeService(raises=InvalidWebhookSignatureError()))
    r = client.post(BASE, content=_captured_body(), headers={"X-Razorpay-Signature": "wrong"})
    assert r.status_code == 401


def test_unconfigured_payments_returns_503(client, monkeypatch):
    _use(monkeypatch, FakeService(raises=PaymentsNotConfiguredError()))
    r = client.post(BASE, content=_captured_body(), headers={"X-Razorpay-Signature": "sig"})
    assert r.status_code == 503


def test_ignored_event_still_returns_200(client, monkeypatch):
    _use(monkeypatch, FakeService(result=WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT)))
    body = json.dumps({"event": "refund.processed", "payload": {}}).encode()
    r = client.post(BASE, content=body, headers={"X-Razorpay-Signature": "sig"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "ignored_event"


def test_already_processed_returns_200_not_an_error(client, monkeypatch):
    """A retried delivery for an already-granted payment is a success from
    Razorpay's point of view -- it must not be told to keep retrying."""
    _use(monkeypatch, FakeService(result=WebhookResult(
        outcome=WebhookOutcome.ALREADY_PROCESSED, payment_id=1)))
    r = client.post(BASE, content=_captured_body(), headers={"X-Razorpay-Signature": "sig"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "already_processed"


def test_malformed_json_body_does_not_crash_the_route(client, monkeypatch):
    """The body is used for logging (event/entity extraction) before the
    service ever verifies its signature -- malformed JSON there must degrade
    to an unkeyed log entry, not a 500."""
    service = FakeService(raises=InvalidWebhookSignatureError())
    _use(monkeypatch, service)
    r = client.post(BASE, content=b"not json at all", headers={"X-Razorpay-Signature": "sig"})
    assert r.status_code == 401   # reaches the service, which rejects the bad signature
