"""PaymentGateway -- Razorpay today, a protocol so a second gateway is a
channel added later, not a redesign (same shape as app.admin.health's
AlertChannel).

RazorpayGateway is a thin httpx wrapper over Razorpay's plain REST API (Orders
for one-time purchases, Plans/Subscriptions/Invoices for the recurring tiers),
not the `razorpay` PyPI SDK -- one fewer third-party dependency to trust for a
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
    """What the gateway hands back for one recurring mandate.

    `status` is Razorpay's own word for it and is almost always `created` at
    this point: the founder has not authorised anything yet, and will not until
    they complete Checkout. Nothing here grants access -- see
    app/payments/subscriptions.py, where only `subscription.charged` does.
    """

    subscription_id: str
    status: str
    plan_id: str
    #: Razorpay's hosted authorisation page. Kept because it is the fallback
    #: when Checkout.js cannot be opened; the normal path passes
    #: `subscription_id` to the widget instead.
    short_url: str | None = None
    current_start: int | None = None
    current_end: int | None = None
    charge_at: int | None = None


@dataclass(frozen=True)
class GatewayPlan:
    """A Razorpay Plan. Its amount and period are IMMUTABLE once created --
    Razorpay will not let them be edited -- so a price change means creating a
    new plan and migrating new customers to it (guide step 4). That is why
    `razorpay_plans` keeps superseded rows rather than updating one."""

    plan_id: str
    amount_paise: int
    period: str
    interval: int


class PaymentGateway(Protocol):
    def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder: ...

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool: ...

    def verify_checkout_signature(
        self, *, order_id: str, payment_id: str, signature: str
    ) -> bool: ...

    def fetch_payment(self, payment_id: str) -> dict: ...

    # --- recurring ---------------------------------------------------------

    def create_plan(
        self, *, period: str, interval: int, amount_paise: int, currency: str,
        name: str, description: str, notes: dict[str, str],
    ) -> GatewayPlan: ...

    def create_subscription(
        self, *, plan_id: str, total_count: int, notes: dict[str, str],
        customer_notify: bool = True,
    ) -> GatewaySubscription: ...

    def fetch_subscription(self, subscription_id: str) -> dict: ...

    def cancel_subscription(
        self, subscription_id: str, *, at_cycle_end: bool
    ) -> dict: ...

    def fetch_invoice(self, invoice_id: str) -> dict: ...


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
    """Orders API + Subscriptions API + the webhook signature check Razorpay's
    own docs specify (raw body, signed with the webhook secret). The signature
    check is not optional -- an unsigned or wrongly-signed payload must never
    be trusted as "payment succeeded".

    The two product APIs answer two different questions and are kept apart on
    purpose. An ORDER is money that arrives once (Starter Rs 199): create it,
    charge it, done. A SUBSCRIPTION is a mandate to charge repeatedly (Plus
    Rs 499, Pro Rs 999): it is created unpaid, authorised by the founder, and
    then charged by Razorpay every month with no further involvement from this
    backend until the webhook lands. Using an order for a recurring tier is
    what this codebase did before, and it meant the second month never came.

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
                    # Auto-capture: an Order is the ONE-TIME path (Starter
                    # Rs 199 and credit top-ups), where the money arrives once
                    # and there is no later "capture" step to hold open.
                    # Recurring tiers do not come through here at all --
                    # `create_subscription` below is their path, and Razorpay
                    # captures each cycle's charge itself.
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

    # --- recurring: Plans, Subscriptions, Invoices --------------------------
    #
    # A different Razorpay product from Orders, and the reason Plus and Pro can
    # renew at all. The division of labour is the same one the rest of this
    # module keeps: these methods TALK to Razorpay and return what it said.
    # None of them decides that a founder may have a plan -- that is
    # app/payments/subscriptions.py's job, and it only ever acts on
    # `subscription.charged`, never on a subscription merely existing.

    def _call(self, method: str, path: str, *, what: str, json: dict | None = None) -> dict:
        """One shaped request, so five endpoints do not carry five copies of
        the same error handling. Same two-tier error reporting the Orders calls
        above already use: Razorpay's status and `error.description` go to the
        log, a plain message goes to the founder."""
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

    def create_plan(
        self, *, period: str, interval: int, amount_paise: int, currency: str,
        name: str, description: str, notes: dict[str, str],
    ) -> GatewayPlan:
        """Create the Rs 499 / Rs 999 Razorpay Plan a subscription is billed on.

        Called once per tier per mode from the admin panel, not on any founder's
        path. Razorpay treats a plan's amount and period as immutable, so this
        is deliberately not an upsert: re-running it makes a SECOND plan, which
        is exactly the right behaviour for a price change and exactly the wrong
        one to do by accident. `razorpay_plans`' unique index on (tier, mode)
        where is_active is what stops two live plans for one tier.
        """
        data = self._call(
            "POST", "/plans", what="plan creation",
            json={
                "period": period,
                "interval": interval,
                "item": {
                    "name": name,
                    "description": description,
                    "amount": amount_paise,
                    "currency": currency,
                },
                "notes": notes,
            },
        )
        item = data.get("item") or {}
        return GatewayPlan(
            plan_id=data["id"],
            # Read back from Razorpay rather than echoing the argument: if it
            # created the plan for a different amount than we asked, the caller
            # must be able to see that before any founder is billed on it.
            amount_paise=int(item.get("amount") or 0),
            period=str(data.get("period") or period),
            interval=int(data.get("interval") or interval),
        )

    def create_subscription(
        self, *, plan_id: str, total_count: int, notes: dict[str, str],
        customer_notify: bool = True,
    ) -> GatewaySubscription:
        """Create the mandate the founder is about to authorise.

        `total_count` is how many billing cycles Razorpay will attempt before
        the subscription completes on its own. Razorpay requires a finite
        number -- there is no "until cancelled" -- so the caller passes a long
        horizon and the subscription ends by cancellation long before it is
        reached (see app/payments/subscriptions.py).

        `customer_notify=True` leaves Razorpay's own charge and failure emails
        on. They are the notification the guide's failed-payment step asks for,
        sent by the party that actually knows the charge failed, and they keep
        arriving whether or not this backend is up.
        """
        data = self._call(
            "POST", "/subscriptions", what="subscription creation",
            json={
                "plan_id": plan_id,
                "total_count": total_count,
                "customer_notify": 1 if customer_notify else 0,
                "notes": notes,
            },
        )
        return _to_subscription(data)

    def fetch_subscription(self, subscription_id: str) -> dict:
        """Read one subscription entity straight from Razorpay -- the
        authoritative answer to "is this mandate still active, and when does it
        charge next?". Used to reconcile a subscription whose webhook was
        missed, and as the read-back after a cancellation."""
        return self._call("GET", f"/subscriptions/{subscription_id}",
                          what="subscription fetch")

    def cancel_subscription(self, subscription_id: str, *, at_cycle_end: bool) -> dict:
        """Cancel a mandate, either at the end of the paid period or now.

        `at_cycle_end=True` is the default the product should almost always
        use: the founder has paid for this month, and taking it away the
        instant they click Cancel is charging for something not delivered. It
        is also what lets the confirmation screen state a real date. Razorpay
        keeps billing nothing further either way; the difference is only when
        the mandate stops.
        """
        return self._call(
            "POST", f"/subscriptions/{subscription_id}/cancel",
            what="subscription cancellation",
            json={"cancel_at_cycle_end": 1 if at_cycle_end else 0},
        )

    def fetch_invoice(self, invoice_id: str) -> dict:
        """Read one invoice entity. The webhook's own payload carries the
        invoice, so this is for reconciliation and for the founder asking for a
        receipt whose webhook never arrived."""
        return self._call("GET", f"/invoices/{invoice_id}", what="invoice fetch")


def _to_subscription(data: dict) -> GatewaySubscription:
    """Razorpay's subscription entity, narrowed to what this codebase mirrors.

    Every timestamp stays a raw epoch int here. Converting is the service
    layer's job and it does it in one place -- a dataclass that sometimes held
    an int and sometimes a datetime is how a period end ends up 56 years in the
    past.
    """
    def _epoch(key: str) -> int | None:
        value = data.get(key)
        return int(value) if isinstance(value, (int, float)) and value else None

    return GatewaySubscription(
        subscription_id=str(data.get("id") or ""),
        status=str(data.get("status") or ""),
        plan_id=str(data.get("plan_id") or ""),
        short_url=data.get("short_url") or None,
        current_start=_epoch("current_start"),
        current_end=_epoch("current_end"),
        charge_at=_epoch("charge_at"),
    )
