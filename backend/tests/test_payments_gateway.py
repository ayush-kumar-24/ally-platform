"""RazorpayGateway -- the thin httpx wrapper over Razorpay's REST API.

Uses httpx.MockTransport (part of httpx itself, no extra dependency) to
drive real request/response handling through the real client, rather than
mocking the gateway class's own methods -- this is what actually proves the
Basic Auth, the request body shape, and the two HMAC checks are correct.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest

from app.payments.gateway import GatewayOrder, PaymentGatewayError, RazorpayGateway


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="https://api.razorpay.com/v1", auth=("rzp_test_key", "test_secret"))


def _gateway(handler=None, *, webhook_secret="whsec_test") -> RazorpayGateway:
    client = _client(handler) if handler else None
    return RazorpayGateway(key_id="rzp_test_key", key_secret="test_secret",
                           webhook_secret=webhook_secret, client=client)


# --- construction ------------------------------------------------------------

def test_missing_key_id_refuses_to_construct():
    with pytest.raises(PaymentGatewayError):
        RazorpayGateway(key_id="", key_secret="secret", webhook_secret="whsec")


def test_missing_key_secret_refuses_to_construct():
    with pytest.raises(PaymentGatewayError):
        RazorpayGateway(key_id="rzp_test", key_secret="", webhook_secret="whsec")


# --- create_order --------------------------------------------------------

def test_create_order_sends_basic_auth_and_the_right_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "order_abc123", "amount": 45000, "currency": "INR"})

    order = _gateway(handler).create_order(
        amount_paise=45000, currency="INR", receipt="founder-1-starter-1234",
        notes={"founder_id": "1", "plan_tier": "starter"},
    )

    assert order == GatewayOrder(order_id="order_abc123", amount_paise=45000, currency="INR")
    assert captured["auth"] and captured["auth"].startswith("Basic ")
    assert captured["body"]["amount"] == 45000
    assert captured["body"]["currency"] == "INR"
    assert captured["body"]["receipt"] == "founder-1-starter-1234"
    assert captured["body"]["payment_capture"] == 1
    assert captured["body"]["notes"] == {"founder_id": "1", "plan_tier": "starter"}


def test_create_order_raises_on_gateway_error_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"description": "bad request"}})

    with pytest.raises(PaymentGatewayError):
        _gateway(handler).create_order(amount_paise=100, currency="INR", receipt="r1", notes={})


def test_create_order_error_carries_razorpays_status_and_description():
    """What the backend log must say when checkout fails in an environment:
    a 401 here means the configured key id/secret are wrong or mismatched,
    which no amount of retrying fixes. `str(exc)` used to say only
    "Client error '401 Unauthorized' for url ..."."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "BAD_REQUEST_ERROR",
                                                   "description": "Authentication failed"}})

    with pytest.raises(PaymentGatewayError) as info:
        _gateway(handler).create_order(amount_paise=100, currency="INR", receipt="r1", notes={})
    assert info.value.status_code == 401
    assert info.value.gateway_message == "BAD_REQUEST_ERROR Authentication failed"
    assert "401" in str(info.value) and "Authentication failed" in str(info.value)


def test_create_order_error_survives_a_non_json_error_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(PaymentGatewayError) as info:
        _gateway(handler).create_order(amount_paise=100, currency="INR", receipt="r1", notes={})
    assert info.value.status_code == 502
    assert info.value.gateway_message is None


def test_create_order_raises_on_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(PaymentGatewayError):
        _gateway(handler).create_order(amount_paise=100, currency="INR", receipt="r1", notes={})


# --- verify_webhook_signature ---------------------------------------------

def test_webhook_signature_accepts_a_correctly_signed_body():
    gateway = _gateway(webhook_secret="whsec_live")
    body = b'{"event": "payment.captured"}'
    signature = hmac.new(b"whsec_live", body, hashlib.sha256).hexdigest()
    assert gateway.verify_webhook_signature(body=body, signature=signature) is True


def test_webhook_signature_rejects_a_tampered_body():
    gateway = _gateway(webhook_secret="whsec_live")
    body = b'{"event": "payment.captured"}'
    signature = hmac.new(b"whsec_live", body, hashlib.sha256).hexdigest()
    tampered = b'{"event": "payment.captured", "extra": "injected"}'
    assert gateway.verify_webhook_signature(body=tampered, signature=signature) is False


def test_webhook_signature_fails_closed_with_no_secret_configured():
    """No webhook secret means no signature can ever be verified -- fail
    closed, not "any signature passes"."""
    gateway = _gateway(webhook_secret="")
    body = b'{"event": "payment.captured"}'
    signature = hmac.new(b"anything", body, hashlib.sha256).hexdigest()
    assert gateway.verify_webhook_signature(body=body, signature=signature) is False
