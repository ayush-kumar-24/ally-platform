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
    a clear "try again" rather than swallowing it.

    `status_code` and `gateway_message` carry what Razorpay actually said
    (its HTTP status and the `error.description` from its JSON body) when
    there is one. They exist for the log line, never for the founder: a
    401 "Authentication failed" means the key id/secret on the server are
    wrong or mismatched, a 400 names the bad field, and neither is anything
    a founder can act on -- but both are exactly what whoever reads the
    backend log needs, and the plain `str(exc)` used to say only
    "Client error '401 Unauthorized' for url ...".
    """

    def __init__(self, message: str, *, status_code: int | None = None,
                 gateway_message: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.gateway_message = gateway_message


@dataclass(frozen=True)
class GatewayOrder:
    """What the gateway hands back for one checkout attempt. `amount_paise`
    and `currency` echo the gateway's own confirmation of what it created an
    order for -- read back rather than assumed, so a mismatch (e.g. currency
    rounding) is visible instead of silently trusted."""

    order_id: str
    amount_paise: int
    currency: str


@dataclass(frozen=True)
class GatewaySubscription:
    """A Razorpay subscription as created -- the founder authorises it (and pays
    the trial fee) in Checkout.js using `subscription_id`."""

    subscription_id: str
    status: str


class PaymentGateway(Protocol):
    def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder: ...

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool: ...

    def verify_checkout_signature(
        self, *, order_id: str, payment_id: str, signature: str
    ) -> bool: ...

    def fetch_payment(self, payment_id: str) -> dict: ...

    # --- trial + autopay (app/payments/subscriptions.py) ---

    def create_subscription(
        self, *, plan_id: str, total_count: int, start_at: int, offer_id: str,
        upfront_amount_paise: int, upfront_label: str, expire_by: int,
        notes: dict[str, str],
    ) -> GatewaySubscription: ...

    def fetch_subscription(self, subscription_id: str) -> dict: ...

    def cancel_subscription(self, subscription_id: str, *, at_cycle_end: bool) -> dict: ...

    def fetch_invoice(self, invoice_id: str) -> dict: ...

    def verify_subscription_checkout_signature(
        self, *, subscription_id: str, payment_id: str, signature: str
    ) -> bool: ...


def _error_description(resp: httpx.Response) -> str | None:
    """Razorpay's error body is `{"error": {"code": ..., "description": ...}}`.
    Read defensively: a gateway outage can answer with an HTML page or an
    empty body, and a diagnostic helper must never be the thing that throws."""
    try:
        error = resp.json().get("error") or {}
    except ValueError:
        return None
    if not isinstance(error, dict):
        return None
    parts = [str(error[k]) for k in ("code", "description") if error.get(k)]
    return " ".join(parts) or None


class RazorpayGateway:
    """Orders API (create) + the webhook signature check Razorpay's own docs
    specify (raw body, signed with the webhook secret). It is not optional --
    an unsigned or wrongly-signed payload must never be trusted as "payment
    succeeded".

    `verify_checkout_signature` and `fetch_payment` exist for the second,
    founder-initiated confirmation path (PaymentService.confirm_checkout).
    Neither makes the browser authoritative: the signature only proves the
    callback this tab is quoting really came from Razorpay for this order,
    and the *grant* still hangs on `fetch_payment` -- a server-to-server read
    of Razorpay's own payment entity, authenticated with the key secret. A
    founder who forges a callback gets a signature failure; one who somehow
    forges past that gets a fetch that says the payment is not captured.
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
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            gateway_message = _error_description(exc.response)
            raise PaymentGatewayError(
                f"razorpay: order creation failed: HTTP {status_code}"
                + (f": {gateway_message}" if gateway_message else ""),
                status_code=status_code, gateway_message=gateway_message,
            ) from exc
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"razorpay: order creation failed: {exc}") from exc

        data = resp.json()
        return GatewayOrder(
            order_id=data["id"], amount_paise=data["amount"], currency=data["currency"]
        )

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            # No secret configured means no webhook can ever be verified --
            # fail closed, not "any signature passes".
            return False
        expected = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def verify_checkout_signature(
        self, *, order_id: str, payment_id: str, signature: str
    ) -> bool:
        """Razorpay's Checkout.js handler signature: HMAC-SHA256 of
        `order_id|payment_id` under the KEY secret (not the webhook secret).

        It proves the callback the browser is quoting was minted by Razorpay
        for this order -- nothing more. It is not on its own permission to
        grant a plan: `fetch_payment` below is what settles that.
        """
        if not order_id or not payment_id:
            return False
        expected = hmac.new(
            self.key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def fetch_payment(self, payment_id: str) -> dict:
        """Read one payment entity straight from Razorpay.

        This is the authoritative answer to "did this actually get captured?"
        -- a server-to-server call under the key secret, with the same shape of
        entity (`id`, `order_id`, `status`, `notes`) the webhook delivers, so
        one grant path can serve both.
        """
        try:
            resp = self._client.get(f"/payments/{payment_id}")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            gateway_message = _error_description(exc.response)
            raise PaymentGatewayError(
                f"razorpay: payment fetch failed: HTTP {status_code}"
                + (f": {gateway_message}" if gateway_message else ""),
                status_code=status_code, gateway_message=gateway_message,
            ) from exc
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"razorpay: payment fetch failed: {exc}") from exc

        data = resp.json()
        return data if isinstance(data, dict) else {}

    # --- trial + autopay ------------------------------------------------------

    def _call(self, method: str, path: str, what: str, json: dict | None = None) -> dict:
        try:
            resp = self._client.request(method, path, json=json)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            gateway_message = _error_description(exc.response)
            raise PaymentGatewayError(
                f"razorpay: {what} failed: HTTP {status_code}"
                + (f": {gateway_message}" if gateway_message else ""),
                status_code=status_code, gateway_message=gateway_message,
            ) from exc
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"razorpay: {what} failed: {exc}") from exc
        data = resp.json()
        return data if isinstance(data, dict) else {}

    def create_subscription(
        self, *, plan_id: str, total_count: int, start_at: int, offer_id: str,
        upfront_amount_paise: int, upfront_label: str, expire_by: int,
        notes: dict[str, str],
    ) -> GatewaySubscription:
        """A subscription whose first charge is `start_at` (end of the trial).

        The trial fee rides as an upfront ADDON, which Razorpay charges in the
        same transaction that authorises the mandate -- so the founder pays the
        fee and sets up autopay in one step, and a founder who cannot set up
        autopay is never charged the fee. `offer_id` takes the fee back off the
        first cycle's charge (see settings.RAZORPAY_TRIAL_OFFER_ID_*).
        """
        data = self._call("POST", "/subscriptions", "subscription creation", json={
            "plan_id": plan_id,
            "total_count": total_count,
            "quantity": 1,
            "start_at": start_at,
            "expire_by": expire_by,
            "customer_notify": 1,
            "offer_id": offer_id,
            "addons": [{"item": {"name": upfront_label, "amount": upfront_amount_paise,
                                 "currency": "INR"}}],
            "notes": notes,
        })
        return GatewaySubscription(subscription_id=data["id"], status=data.get("status", ""))

    def fetch_subscription(self, subscription_id: str) -> dict:
        return self._call("GET", f"/subscriptions/{subscription_id}", "subscription fetch")

    def cancel_subscription(self, subscription_id: str, *, at_cycle_end: bool) -> dict:
        return self._call("POST", f"/subscriptions/{subscription_id}/cancel",
                          "subscription cancel",
                          json={"cancel_at_cycle_end": 1 if at_cycle_end else 0})

    def fetch_invoice(self, invoice_id: str) -> dict:
        """Subscription payments arrive with an `invoice_id` and an order this
        backend never created; the invoice is what names the subscription."""
        return self._call("GET", f"/invoices/{invoice_id}", "invoice fetch")

    def verify_subscription_checkout_signature(
        self, *, subscription_id: str, payment_id: str, signature: str
    ) -> bool:
        """Checkout.js's handler signature for a subscription: HMAC-SHA256 of
        `payment_id|subscription_id` under the key secret -- the reverse order
        of the order flow's `order_id|payment_id`."""
        if not subscription_id or not payment_id:
            return False
        expected = hmac.new(
            self.key_secret.encode(), f"{payment_id}|{subscription_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")
