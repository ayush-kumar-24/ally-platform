"""PaymentGateway -- Razorpay today, a protocol so a second gateway is a
channel added later, not a redesign (same shape as app.admin.health's
AlertChannel).

RazorpayGateway is a thin httpx wrapper over Razorpay's plain REST API, not
the `razorpay` PyPI SDK -- one fewer third-party dependency to trust for a
handful of documented endpoints, and it stays consistent with how this
codebase already talks to a vendor's HTTP API (object_storage.py's boto3
call shape aside, reports/gotenberg.py's is_available() is the closer
sibling: a small, deliberately thin wrapper, not a vendored client).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol

import httpx

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class PaymentGatewayError(Exception):
    """Any failure talking to the gateway. There is usually no fallback --
    a founder cannot pay through anything else -- so callers surface this as
    a clear "try again" rather than swallowing it."""


@dataclass(frozen=True)
class GatewayOrder:
    """What the gateway hands back for one checkout attempt. `amount_paise`
    and `currency` echo the gateway's own confirmation of what it created an
    order for -- read back rather than assumed, so a mismatch (e.g. currency
    rounding) is visible instead of silently trusted."""

    order_id: str
    amount_paise: int
    currency: str


class PaymentGateway(Protocol):
    def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder: ...

    def verify_payment_signature(
        self, *, order_id: str, payment_id: str, signature: str
    ) -> bool: ...

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool: ...


class RazorpayGateway:
    """Orders API (create) + the two HMAC checks Razorpay's own docs specify:
    the checkout-callback signature (order_id|payment_id, signed with the key
    secret) and the webhook signature (raw body, signed with the separate
    webhook secret). Neither is optional -- an unsigned or wrongly-signed
    payload must never be trusted as "payment succeeded".
    """

    def __init__(
        self,
        *,
        key_id: str,
        key_secret: str,
        webhook_secret: str,
        client: httpx.Client | None = None,
    ):
        if not key_id or not key_secret:
            raise PaymentGatewayError("Razorpay is not configured (missing key id/secret)")
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self._client = client or httpx.Client(
            auth=(key_id, key_secret), timeout=15.0, base_url=RAZORPAY_API_BASE
        )

    def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder:
        try:
            resp = self._client.post(
                "/orders",
                json={
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": receipt,
                    # Auto-capture: this checkout is a single one-time order per
                    # billing period (see app/payments/__init__.py), not
                    # Razorpay's separate Subscriptions product, so there is no
                    # later "capture" step to hold open.
                    "payment_capture": 1,
                    # Razorpay copies order notes onto the payment entity, so
                    # this is how `founder_id`/`plan_tier` survive to the
                    # webhook -- `payments` has no such column, and this reads
                    # the intent back from the gateway instead of needing one.
                    "notes": notes,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"razorpay: order creation failed: {exc}") from exc

        data = resp.json()
        return GatewayOrder(
            order_id=data["id"], amount_paise=data["amount"], currency=data["currency"]
        )

    def verify_payment_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        """The checkout widget's own callback signature -- confirms the
        redirect actually came from Razorpay. NOT what grants the plan (the
        webhook is, see PaymentService.handle_webhook's own note); this is
        only ever used to decide what the frontend is told about the attempt
        it just made."""
        expected = hmac.new(
            self.key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            # No secret configured means no webhook can ever be verified --
            # fail closed, not "any signature passes".
            return False
        expected = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")
