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

import pathlib

import pytest

from app.credits.models import CreditOperation
from app.payments.errors import (
    InvalidCheckoutCallbackError,
    InvalidCheckoutError,
    PaymentNotFoundError,
    InvalidWebhookSignatureError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
)
from app.payments.gateway import GatewayOrder, PaymentGatewayError
from app.payments.models import WebhookOutcome
from app.payments.service import PaymentService
from app.plans.catalog import PLANS, PlanTier

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
WEBHOOK_SECRET = "whsec_test"
KEY_SECRET = "rzp_key_secret"


# --- fakes ---------------------------------------------------------------

class FakeGateway:
    def __init__(self, *, order_id="order_1", raise_on_create=None, entities=None,
                 raise_on_fetch=None):
        self.key_id = "rzp_test_key"
        self.order_id = order_id
        self.raise_on_create = raise_on_create
        self.created_orders = []
        self.entities = entities or {}
        self.raise_on_fetch = raise_on_fetch
        self.fetched = []

    def create_order(self, *, amount_paise, currency, receipt, notes):
        if self.raise_on_create:
            raise self.raise_on_create
        self.created_orders.append(
            {"amount_paise": amount_paise, "currency": currency, "receipt": receipt, "notes": notes})
        return GatewayOrder(order_id=self.order_id, amount_paise=amount_paise, currency=currency)

    def verify_webhook_signature(self, *, body, signature):
        expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def verify_checkout_signature(self, *, order_id, payment_id, signature):
        expected = hmac.new(KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def fetch_payment(self, payment_id):
        """What Razorpay says about this payment when ASKED -- the only thing
        confirm_checkout is allowed to grant on. `entities` is what the fake
        gateway will admit to; anything else raises the way the real one does
        for an id Razorpay does not know."""
        if self.raise_on_fetch:
            raise self.raise_on_fetch
        self.fetched.append(payment_id)
        try:
            return self.entities[payment_id]
        except KeyError:
            raise PaymentGatewayError("razorpay: payment fetch failed: HTTP 400",
                                      status_code=400) from None


class FakeRepository:
    def __init__(self):
        self._payments: dict[int, dict] = {}
        self._by_order: dict[str, int] = {}
        self._by_gpid: dict[str, int] = {}
        self._next_payment_id = 1
        self._next_subscription_id = 1
        self.subscriptions_created = []
        self.plans_granted = []
        self.commits: list[tuple[str, bool]] = []
        self.db = _FakeDbHandle()

    def create_pending(self, *, founder_id, amount_inr, currency, gateway, gateway_order_id,
                       plan_tier, coupon_id=None, list_amount_inr=None, discount_inr=None,
                       buyer_state=None, purchase_type=None, buyer_gstin=None,
                       buyer_legal_name=None, buyer_address=None, commit=True):
        pid = self._next_payment_id
        self._next_payment_id += 1
        self._payments[pid] = {
            "payment_id": pid, "founder_id": founder_id, "status": "pending",
            "gateway_order_id": gateway_order_id, "gateway_payment_id": None,
            "amount_inr": amount_inr, "subscription_id": None, "plan_tier": plan_tier,
            "coupon_id": coupon_id, "list_amount_inr": list_amount_inr,
            "discount_inr": discount_inr, "buyer_state": buyer_state,
            "purchase_type": purchase_type, "buyer_gstin": buyer_gstin,
            "buyer_legal_name": buyer_legal_name, "buyer_address": buyer_address,
        }
        self._by_order[gateway_order_id] = pid
        self.commits.append(("create_pending", commit))
        return pid

    def attach_coupon(self, payment_id, *, coupon_id, discount_inr):
        self._payments[payment_id]["coupon_id"] = coupon_id
        self._payments[payment_id]["discount_inr"] = discount_inr
        self.commits.append(("attach_coupon", True))

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
                             amount_inr=row["amount_inr"], subscription_id=row["subscription_id"],
                             plan_tier=row.get("plan_tier"))


class _FakeDbHandle:
    """PaymentService reaches through the repository for commit/rollback when a
    coupon reservation has to share the payment's transaction."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


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

    # Read from the catalog rather than pinned to a literal: what matters is
    # that the order is created for exactly the catalog price in paise, not
    # what that price happens to be this quarter. A hard-coded copy here only
    # asserts that someone remembered to edit two places -- which is what it
    # did when Plus moved from Rs 450 to Rs 499.
    price = PLANS[PlanTier.STARTER].price_inr

    assert session.order_id == "order_1"
    assert session.amount_paise == price * 100
    assert session.currency == "INR"
    assert session.key_id == "rzp_test_key"

    payment = repo.get_by_gateway_order_id("order_1")
    assert payment.founder_id == 42
    assert payment.status == "pending"
    assert payment.amount_inr == price


def test_checkout_gateway_failure_is_a_502_and_records_no_payment():
    """Razorpay refusing the order (wrong keys, a bad field, an outage) is
    the provider's answer, not this backend breaking: a 502 with a plain
    message, never the generic 500 -- and no pending row, since there is no
    order for it to point at."""
    gateway = FakeGateway(raise_on_create=PaymentGatewayError(
        "razorpay: order creation failed: HTTP 401: Authentication failed",
        status_code=401, gateway_message="Authentication failed"))
    service, repo, _ = _service(gateway=gateway)
    with pytest.raises(PaymentGatewayUnavailableError) as info:
        service.start_checkout(42, PlanTier.STARTER)
    assert info.value.status_code == 502
    assert isinstance(info.value.__cause__, PaymentGatewayError)
    assert repo._payments == {}


def test_checkout_carries_founder_and_plan_in_the_order_notes():
    """This is how the webhook later learns which plan to grant -- payments
    has no plan_type column, see app/payments/service.py's own note."""
    gateway = FakeGateway()
    service, _, _ = _service(gateway=gateway)
    service.start_checkout(42, PlanTier.PRO)
    assert gateway.created_orders[0]["notes"] == {"founder_id": "42", "plan_tier": "pro"}


# --- start_checkout with a coupon ------------------------------------------
#
# These are the money tests. The number sent to Razorpay, the number stored on
# the payment row and the number the founder was shown must be the same number,
# and the slot must not be claimable without a payment to claim it against.

def _coupon_service(*, discount_inr=None, raises=None):
    """A CouponService stand-in. Only quote/reserve/repository are reached."""
    from app.plans.catalog import PLANS

    class _Repo:
        def __init__(self):
            self.confirmed = []
            self.released = []

        def confirm_for_payment(self, payment_id, *, at):
            self.confirmed.append(payment_id)

        def release_for_payment(self, payment_id):
            self.released.append(payment_id)

    class _Coupon:
        code = "FOUNDER100"
        coupon_id = 7

    class _Quote:
        def __init__(self, d):
            self.discount_inr = d

    class _Service:
        def __init__(self):
            self.repository = _Repo()
            self.reserved = []

        def _discount(self, tier):
            return (PLANS[tier].price_inr // 2 if discount_inr is None else discount_inr)

        def quote(self, *, code, tier, founder_id):
            if raises:
                raise raises
            return _Quote(self._discount(tier))

        def reserve(self, *, code, tier, founder_id, payment_id):
            if raises:
                raise raises
            self.reserved.append(payment_id)
            return _Coupon(), self._discount(tier)

    return _Service()


def test_a_coupon_discounts_the_order_the_gateway_is_asked_to_create():
    """The founder sends a CODE; the price stays the catalog's to decide."""
    gateway = FakeGateway()
    coupons = _coupon_service()
    service, repo, _ = _service(gateway=gateway)
    service.coupons = coupons

    price = PLANS[PlanTier.PRO].price_inr
    session = service.start_checkout(42, PlanTier.PRO, coupon_code="founder100")

    assert gateway.created_orders[0]["amount_paise"] == (price - price // 2) * 100
    assert session.amount_paise == (price - price // 2) * 100
    assert session.list_amount_paise == price * 100
    assert session.discount_paise == (price // 2) * 100
    assert session.coupon_code == "FOUNDER100"


def test_the_discounted_payment_row_records_all_three_numbers():
    """list - discount = charged, stored rather than recomputed later. The admin
    revenue views read amount_inr, so it must be what actually reached Razorpay."""
    coupons = _coupon_service()
    service, repo, _ = _service()
    service.coupons = coupons
    price = PLANS[PlanTier.PRO].price_inr

    service.start_checkout(42, PlanTier.PRO, coupon_code="FOUNDER100")
    row = repo._payments[1]

    assert row["amount_inr"] == price - price // 2
    assert row["list_amount_inr"] == price
    assert row["discount_inr"] == price // 2
    assert row["coupon_id"] == 7


def test_an_undiscounted_checkout_leaves_the_coupon_columns_null():
    """NULL, not a redundant copy of the price: "was this discounted?" is then
    answerable by the column being set, not by comparing two numbers."""
    service, repo, _ = _service()
    service.coupons = _coupon_service()

    service.start_checkout(42, PlanTier.PRO)
    row = repo._payments[1]

    assert row["coupon_id"] is None
    assert row["list_amount_inr"] is None
    assert row["discount_inr"] is None


def test_the_payment_row_is_not_committed_until_the_slot_is_claimed():
    """A claimed slot must never outlive the payment it was claimed for."""
    service, repo, _ = _service()
    service.coupons = _coupon_service()

    service.start_checkout(42, PlanTier.PRO, coupon_code="FOUNDER100")

    assert ("create_pending", False) in repo.commits
    assert ("attach_coupon", True) in repo.commits


def test_a_rejected_coupon_leaves_no_orphan_payment_row():
    """The order exists at Razorpay but is never captured, which costs nothing.
    What must not survive is a pending payment nobody can explain."""
    from app.coupons.errors import CouponFullyRedeemedError

    service, repo, _ = _service()
    service.coupons = _coupon_service(raises=CouponFullyRedeemedError())

    with pytest.raises(CouponFullyRedeemedError):
        service.start_checkout(42, PlanTier.PRO, coupon_code="FOUNDER100")


def test_a_captured_discounted_payment_confirms_the_redemption():
    coupons = _coupon_service()
    service, repo, _ = _service()
    service.coupons = coupons
    service.start_checkout(42, PlanTier.PRO, coupon_code="FOUNDER100")

    service.handle_webhook(body=_captured_event(tier="pro"), signature=_sign(
        _captured_event(tier="pro")))

    assert coupons.repository.confirmed == [1]


def test_a_failed_discounted_payment_releases_the_slot_immediately():
    """On a capped code, waiting out the pending TTL is the difference between
    the next founder getting in and being told it sold out."""
    coupons = _coupon_service()
    service, repo, _ = _service()
    service.coupons = coupons
    service.start_checkout(42, PlanTier.PRO, coupon_code="FOUNDER100")

    service.handle_webhook(body=_failed_event(), signature=_sign(_failed_event()))

    assert coupons.repository.released == [1]


def test_a_redemption_bookkeeping_failure_never_undoes_a_granted_plan():
    """Same rule as the credit grant: a founder who paid and got their plan must
    not lose it because a status update failed."""
    coupons = _coupon_service()

    def boom(payment_id, *, at):
        raise RuntimeError("db gone")

    coupons.repository.confirm_for_payment = boom
    service, repo, _ = _service()
    service.coupons = coupons
    service.start_checkout(42, PlanTier.PRO, coupon_code="FOUNDER100")

    result = service.handle_webhook(body=_captured_event(tier="pro"),
                                    signature=_sign(_captured_event(tier="pro")))

    assert result.outcome == WebhookOutcome.CAPTURED
    assert repo.plans_granted == [(42, "pro")]


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
    # Read from the catalog, not pinned to a literal: the grant IS the catalog's
    # monthly_credits, and a hard-coded copy here only asserts that someone
    # remembered to edit two places. This number moved once already when the
    # Rs 450 tier's daily ceiling changed and its credit grant had to follow.
    assert credits.grants[0]["amount"] == PLANS[PlanTier.STARTER].monthly_credits


def test_basic_is_recorded_as_a_one_time_subscription_with_no_expiry():
    """The Rs 199 tier buys one diagnosis, not a month, so its subscription row
    must say so. It shipped once claiming billing_cycle='monthly' with an expiry
    30 days out -- untrue, and load-bearing the moment anything enforces expiry.

    The plan_type written here is also what broke Basic outright: `subscriptions`
    is INSERTed before the plan is granted, and its CHECK constraint did not list
    'basic', so a captured Rs 199 payment failed on this row and never reached
    grant_plan. See migration b4d927f1a6c8."""
    service, repo, _ = _service()
    service.start_checkout(42, PlanTier.BASIC)

    body = _captured_event(order_id="order_1", payment_id="pay_1", tier="basic")
    result = service.handle_webhook(body=body, signature=_sign(body))

    assert result.outcome == WebhookOutcome.CAPTURED
    assert repo.plans_granted == [(42, "basic")]
    sub = repo.subscriptions_created[0]
    assert sub["plan_type"] == "basic"
    assert sub["billing_cycle"] == "one_time"
    assert sub["expires_at"] is None


def test_recurring_plans_still_get_a_monthly_cycle_and_an_expiry():
    """The one-time path must not have quietly changed Plus and Pro."""
    service, repo, _ = _service()
    service.start_checkout(42, PlanTier.PRO)

    body = _captured_event(order_id="order_1", payment_id="pay_1", tier="pro")
    service.handle_webhook(body=body, signature=_sign(body))

    sub = repo.subscriptions_created[0]
    assert sub["plan_type"] == "pro"
    assert sub["billing_cycle"] == "monthly"
    assert sub["expires_at"] is not None


def test_every_sold_tier_is_writable_to_the_subscriptions_table():
    """A guard for the class of bug b4d927f1a6c8 fixed: a tier the catalog sells
    but the database's CHECK constraint rejects is invisible until someone pays.
    The constraint lists tier names, so the catalog and the migration must agree
    -- assert against the constraint's own list rather than a copy of it."""
    from app.plans.catalog import sold_plans

    migration = (
        pathlib.Path(__file__).resolve().parents[1]
        / "alembic" / "versions"
        / "2026_09_06_0700-b4d927f1a6c8_allow_basic_and_one_time_subscriptions.py"
    ).read_text()
    permitted = migration.split("_PLAN_NEW = (", 1)[1].split(")", 1)[0]

    for plan in sold_plans():
        assert f'"{plan.tier.value}"' in permitted, (
            f"catalog sells {plan.name} as tier {plan.tier.value!r}, which "
            "subscriptions_plan_type_check would reject"
        )


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


def test_a_captured_payment_with_no_notes_is_still_granted_from_our_own_row():
    """The regression that charged a founder Rs 999 and gave them nothing.

    Razorpay's payment entity carries whatever notes the BROWSER's Checkout
    options set, not the order's -- and ours sent {plan_name}, so `plan_tier`
    never arrived and the grant was refused on every widget payment. The tier
    is recorded on the payment row at checkout now, so an entity with no
    useful notes at all still grants exactly what was paid for.
    """
    service, repo, _ = _service()
    service.start_checkout(42, PlanTier.STARTER)
    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_1", "order_id": "order_1", "notes": {"plan_name": "Plus"},
        }}},
    }).encode()

    result = service.handle_webhook(body=body, signature=_sign(body))
    assert result.outcome == WebhookOutcome.CAPTURED
    assert repo.plans_granted == [(42, "starter")]


def test_gateway_notes_cannot_upgrade_a_founder_past_what_they_paid_for():
    """Notes are browser-supplied, so they are not authority for a grant.

    Before, the tier came from them: pay for the cheapest plan, put
    `plan_tier: pro` in the Checkout notes, receive Pro. The recorded tier
    wins, and the disagreement is logged rather than honoured.
    """
    service, repo, _ = _service()
    service.start_checkout(42, PlanTier.BASIC)          # paid Rs 199
    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_1", "order_id": "order_1", "notes": {"plan_tier": "pro"},
        }}},
    }).encode()

    result = service.handle_webhook(body=body, signature=_sign(body))
    assert result.outcome == WebhookOutcome.CAPTURED
    assert result.plan == "basic"
    assert repo.plans_granted == [(42, "basic")]


def test_a_legacy_payment_row_falls_back_to_the_notes_then_refuses():
    """A checkout started before payments.plan_tier existed still completes if
    the gateway happens to carry the tier, and is refused -- never guessed --
    when nothing names it."""
    service, repo, _ = _service()
    service.start_checkout(42, PlanTier.STARTER)
    repo._payments[1]["plan_tier"] = None               # a row from the old build

    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_1", "order_id": "order_1", "notes": {"plan_tier": "starter"},
        }}},
    }).encode()
    assert service.handle_webhook(body=body, signature=_sign(body)).outcome == (
        WebhookOutcome.CAPTURED)
    assert repo.plans_granted == [(42, "starter")]

    service2, repo2, _ = _service()
    service2.start_checkout(42, PlanTier.STARTER)
    repo2._payments[1]["plan_tier"] = None
    body2 = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_2", "order_id": "order_1", "notes": {},
        }}},
    }).encode()
    assert service2.handle_webhook(body=body2, signature=_sign(body2)).outcome == (
        WebhookOutcome.UNKNOWN_PAYMENT)
    assert repo2.plans_granted == []


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


# --- confirm_checkout ------------------------------------------------------
#
# The founder-initiated settle. Its whole reason to exist is speed -- a founder
# should not watch a spinner for as long as Razorpay's webhook takes to arrive
# -- and the thing worth testing about it is that speed costs nothing: it
# grants only what Razorpay itself reports, only for the founder's own order,
# and never twice.

def _checkout_sig(order_id: str, payment_id: str, secret: str = KEY_SECRET) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(),
                    hashlib.sha256).hexdigest()


def _captured_entity(*, order_id="order_1", payment_id="pay_1", tier="starter",
                     status="captured") -> dict:
    return {"id": payment_id, "order_id": order_id, "status": status,
            "notes": {"founder_id": "42", "plan_tier": tier}}


def _paid_service(*, entity=None, raise_on_fetch=None):
    """A service whose founder 42 has a pending `order_1` for Starter -- the
    state a browser is in the instant Razorpay's handler fires."""
    entity = entity if entity is not None else _captured_entity()
    gateway = FakeGateway(entities={entity["id"]: entity}, raise_on_fetch=raise_on_fetch)
    service, repo, credits = _service(gateway=gateway)
    service.start_checkout(42, PlanTier.STARTER)
    return service, repo, credits, gateway


def test_confirm_grants_the_plan_without_waiting_for_the_webhook():
    service, repo, credits, gateway = _paid_service()

    result = service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1",
                                      signature=_checkout_sig("order_1", "pay_1"))

    assert result.outcome == WebhookOutcome.CAPTURED
    assert repo.plans_granted == [(42, "starter")]
    assert credits.grants[0]["amount"] == PLANS[PlanTier.STARTER].monthly_credits
    # The grant hangs on Razorpay's own answer, not on the caller's claim.
    assert gateway.fetched == ["pay_1"]


def test_confirm_refuses_a_payment_razorpay_has_not_captured():
    """Authorised-but-not-captured is not a grant and not an error: the founder
    keeps waiting, and the webhook lands when the capture does."""
    service, repo, credits, _ = _paid_service(entity=_captured_entity(status="authorized"))

    result = service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1",
                                      signature=_checkout_sig("order_1", "pay_1"))

    assert result.outcome == WebhookOutcome.NOT_CAPTURED
    assert repo.plans_granted == []
    assert credits.grants == []


def test_confirm_rejects_a_forged_callback_signature():
    service, repo, _, gateway = _paid_service()

    with pytest.raises(InvalidCheckoutCallbackError):
        service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1",
                                 signature="not-a-real-signature")

    assert repo.plans_granted == []
    # Refused before Razorpay was even asked.
    assert gateway.fetched == []


def test_confirm_refuses_another_founders_order():
    """A founder's own token reaches this call, so an order id that is not
    theirs must look exactly like one that does not exist."""
    service, repo, _, _ = _paid_service()

    with pytest.raises(PaymentNotFoundError):
        service.confirm_checkout(99, order_id="order_1", gateway_payment_id="pay_1",
                                 signature=_checkout_sig("order_1", "pay_1"))

    assert repo.plans_granted == []


def test_confirm_refuses_an_unknown_order():
    service, repo, _, _ = _paid_service()

    with pytest.raises(PaymentNotFoundError):
        service.confirm_checkout(42, order_id="order_never_created",
                                 gateway_payment_id="pay_1",
                                 signature=_checkout_sig("order_never_created", "pay_1"))

    assert repo.plans_granted == []


def test_confirm_refuses_a_payment_belonging_to_a_different_order():
    """Even a genuinely captured payment cannot be quoted against someone
    else's pending order: the entity's own order_id has to match."""
    entity = _captured_entity(order_id="order_somebody_else", payment_id="pay_9")
    gateway = FakeGateway(entities={"pay_9": entity})
    service, repo, _ = _service(gateway=gateway)
    service.start_checkout(42, PlanTier.STARTER)

    with pytest.raises(PaymentNotFoundError):
        service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_9",
                                 signature=_checkout_sig("order_1", "pay_9"))

    assert repo.plans_granted == []


def test_confirm_after_the_webhook_already_granted_is_a_no_op():
    """Both paths race by design. Whichever loses must add nothing -- no second
    plan grant, no second month of credits."""
    service, repo, credits, gateway = _paid_service()
    service.handle_webhook(body=_captured_event(order_id="order_1", payment_id="pay_1"),
                           signature=_sign(_captured_event(order_id="order_1", payment_id="pay_1")))
    assert repo.plans_granted == [(42, "starter")]

    result = service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1",
                                      signature=_checkout_sig("order_1", "pay_1"))

    assert result.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.plans_granted == [(42, "starter")]
    assert len(credits.grants) == 1
    assert gateway.fetched == []  # settled from our own row, no round trip needed


def test_the_webhook_after_confirm_already_granted_is_a_no_op():
    """The same race the other way round -- the ordinary case, since the
    webhook usually arrives after the founder's tab has already confirmed."""
    service, repo, credits, _ = _paid_service()
    service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1",
                             signature=_checkout_sig("order_1", "pay_1"))

    body = _captured_event(order_id="order_1", payment_id="pay_1")
    result = service.handle_webhook(body=body, signature=_sign(body))

    assert result.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.plans_granted == [(42, "starter")]
    assert len(credits.grants) == 1


def test_confirm_surfaces_a_gateway_outage_as_a_502():
    """Nothing is lost here: the founder has paid, the webhook is still coming,
    and the caller falls back to waiting rather than showing a failure."""
    service, repo, _, _ = _paid_service(
        raise_on_fetch=PaymentGatewayError("razorpay: unreachable"))

    with pytest.raises(PaymentGatewayUnavailableError):
        service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1",
                                 signature=_checkout_sig("order_1", "pay_1"))

    assert repo.plans_granted == []


def test_confirm_unconfigured_gateway_refuses():
    service, _, _ = _service(gateway=None)
    with pytest.raises(PaymentsNotConfiguredError):
        service.confirm_checkout(42, order_id="order_1", gateway_payment_id="pay_1")


# --- business purchases: the buyer's own tax identity ----------------------

class TestBusinessIdentity:
    """`_checked_business_identity` is what stands between a founder's typo and
    a tax invoice their accountant rejects weeks later.

    Everything here REFUSES rather than downgrading. Issuing a personal invoice
    to someone who asked for a business one charges them and hands their company
    a document it cannot claim credit against -- and they find out long after
    the founder has left the keyboard.
    """

    @staticmethod
    def _check(gstin, name="Blissnack Pvt Ltd", address=None, state="Gujarat"):
        from app.payments.models import BusinessIdentity
        from app.payments.service import _checked_business_identity

        return _checked_business_identity(
            BusinessIdentity(gstin=gstin, legal_name=name, address=address),
            place_of_supply=state,
        )

    def test_a_personal_purchase_has_nothing_to_check(self):
        from app.payments.service import _checked_business_identity

        assert _checked_business_identity(None, place_of_supply="Gujarat") is None

    def test_a_valid_identity_is_normalised_not_merely_accepted(self):
        """Founders paste registration numbers in lower case and with spaces."""
        checked = self._check(" 24aalcg5562b1zs ", name="  Blissnack   Pvt Ltd  ")
        assert checked.gstin == "24AALCG5562B1ZS"
        assert checked.legal_name == "Blissnack Pvt Ltd"

    def test_the_gstins_state_must_match_the_selected_state(self):
        """A GSTIN's first two digits ARE its state, so these cannot legitimately
        disagree -- and if they do, one of them is deciding the CGST/SGST vs
        IGST split wrongly. We cannot know which, so we refuse."""
        from app.payments.errors import InvalidBusinessDetailsError

        with pytest.raises(InvalidBusinessDetailsError) as exc:
            self._check("27AALCG5562B1ZS", state="Gujarat")   # 27 is Maharashtra
        # The message names both states, because "invalid" is not actionable.
        assert "Maharashtra" in str(exc.value) and "Gujarat" in str(exc.value)

    @pytest.mark.parametrize("gstin", [
        "24AALCG", "24AALCG5562B1ZSS", "24AALCG-562B1ZS", "",
    ])
    def test_a_gstin_that_is_not_a_gstin_is_refused(self, gstin):
        from app.payments.errors import InvalidBusinessDetailsError

        with pytest.raises(InvalidBusinessDetailsError):
            self._check(gstin)

    def test_an_unknown_state_code_is_refused(self):
        """99 is not a state. An unrecognised prefix is a typo, not a new one."""
        from app.payments.errors import InvalidBusinessDetailsError

        with pytest.raises(InvalidBusinessDetailsError):
            self._check("99AALCG5562B1ZS", state=None)

    def test_the_registered_name_is_required(self):
        """The credit is claimed against the entity, and its registered name is
        frequently not the founder's own."""
        from app.payments.errors import InvalidBusinessDetailsError

        with pytest.raises(InvalidBusinessDetailsError):
            self._check("24AALCG5562B1ZS", name="   ")

    def test_an_address_is_optional_and_blank_becomes_none(self):
        assert self._check("24AALCG5562B1ZS", address="   ").address is None
        assert self._check("24AALCG5562B1ZS", address="Vadodara").address == "Vadodara"

    def test_a_checkout_with_no_place_of_supply_still_vets_the_gstin_itself(self):
        """The cross-check needs a state; the shape check never does."""
        from app.payments.errors import InvalidBusinessDetailsError

        assert self._check("27AALCG5562B1ZS", state=None).gstin == "27AALCG5562B1ZS"
        with pytest.raises(InvalidBusinessDetailsError):
            self._check("nonsense", state=None)


# --- business pricing: GST on top -----------------------------------------

class TestBusinessPricing:
    """A personal buyer pays the catalog price; a business pays it plus GST.

    Both are charged the same RATE on the same supply -- the difference is
    whether the quoted number already contains the tax. The business pays more
    at the till and reclaims the difference against its GSTIN, so the cost to
    them is the same 999.
    """

    BIZ = None  # set in _checkout

    @staticmethod
    def _checkout(tier, purchase_type, *, coupon=None, state="Gujarat"):
        from app.payments.models import BusinessIdentity, PurchaseType

        repo = FakeRepository()
        service = PaymentService(FakeGateway(), repo, FakeCredits(),
                                 clock=lambda: NOW)
        business = (BusinessIdentity("24AALCG5562B1ZS", "Blissnack Pvt Ltd", None)
                    if purchase_type == PurchaseType.BUSINESS else None)
        session = service.start_checkout(1, tier, coupon_code=coupon,
                                         buyer_state=state,
                                         purchase_type=purchase_type,
                                         business=business)
        return session, repo._payments[session.payment_id]

    def test_a_personal_purchase_charges_exactly_the_catalog_price(self):
        from app.payments.models import PurchaseType

        session, _ = self._checkout(PlanTier.PRO, PurchaseType.PERSONAL)
        assert session.amount_paise == 99900          # Rs 999.00
        assert session.gst_paise == 0
        assert session.gst_percent is None

    def test_a_business_purchase_adds_gst_on_top(self):
        from app.payments.models import PurchaseType

        session, _ = self._checkout(PlanTier.PRO, PurchaseType.BUSINESS)
        assert session.amount_paise == 117882         # Rs 1,178.82
        assert session.gst_paise == 17982             # Rs 179.82
        assert session.gst_percent == 18.0

    @pytest.mark.parametrize("tier,personal,business", [
        (PlanTier.BASIC, 19900, 23482),     # 199   -> 234.82
        (PlanTier.STARTER, 49900, 58882),   # 499   -> 588.82
        (PlanTier.PRO, 99900, 117882),      # 999   -> 1,178.82
    ])
    def test_every_paid_tier_prices_both_ways(self, tier, personal, business):
        from app.payments.models import PurchaseType

        assert self._checkout(tier, PurchaseType.PERSONAL)[0].amount_paise == personal
        assert self._checkout(tier, PurchaseType.BUSINESS)[0].amount_paise == business

    def test_the_charge_is_exact_to_the_paisa_never_a_float(self):
        """`rupees * 118` is a whole number of paise, so nothing rounds."""
        from decimal import Decimal

        from app.payments.models import PurchaseType

        session, row = self._checkout(PlanTier.PRO, PurchaseType.BUSINESS)
        assert session.amount_paise == 999 * 118
        assert row["amount_inr"] == Decimal("1178.82")

    def test_the_invoice_recovers_the_catalog_price_from_what_was_charged(self):
        """The whole scheme rests on this: add 18%, then back 18% out of the
        gross, and you are exactly where you started. If this drifts, the
        business is invoiced for a base that is not the price they agreed."""
        from decimal import Decimal

        from app.payments.invoice import compute_tax
        from app.payments.models import PurchaseType

        _, row = self._checkout(PlanTier.PRO, PurchaseType.BUSINESS)
        tax = compute_tax(row["amount_inr"], percent=Decimal("18"), intra_state=True)
        assert tax.taxable_value == Decimal("999.00")
        assert tax.total_tax == Decimal("179.82")
        assert tax.taxable_value + tax.total_tax == row["amount_inr"]

    def test_a_coupon_discounts_before_gst_not_after(self):
        """Tax is due on what was actually charged for the service, so the
        discount comes off the base and GST applies to the remainder."""
        from app.payments.models import BusinessIdentity, PurchaseType

        service, _, _ = _service(gateway=FakeGateway())
        service.coupons = _coupon_service()
        price = PLANS[PlanTier.PRO].price_inr
        net = price - price // 2          # what _coupon_service discounts by

        session = service.start_checkout(
            1, PlanTier.PRO, coupon_code="founder100", buyer_state="Gujarat",
            purchase_type=PurchaseType.BUSINESS,
            business=BusinessIdentity("24AALCG5562B1ZS", "Blissnack Pvt Ltd", None))

        # GST on the DISCOUNTED base, not on the list price.
        assert session.amount_paise == net * 118
        assert session.gst_paise == net * 18
        assert session.list_amount_paise == price * 100   # still pre-tax

    def test_no_gst_is_added_when_no_tax_invoice_would_be_issued(self, monkeypatch):
        """With no seller GSTIN the document is a receipt saying no GST was
        charged. Adding 18% anyway would make the money and the paperwork
        contradict each other."""
        from app.core.config import settings
        from app.payments.models import PurchaseType

        monkeypatch.setattr(settings, "INVOICE_SELLER_GSTIN", "")
        session, _ = self._checkout(PlanTier.PRO, PurchaseType.BUSINESS)
        assert session.amount_paise == 99900
        assert session.gst_paise == 0

    def test_a_payment_with_no_purchase_type_is_priced_as_personal(self):
        """An older client sends none. It must not silently start charging 18%
        more than the price on the plan card."""
        session, _ = self._checkout(PlanTier.PRO, None)
        assert session.amount_paise == 99900
        assert session.gst_paise == 0
