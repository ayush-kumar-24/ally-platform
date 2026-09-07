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
    InvalidCheckoutError,
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
        self.commits: list[tuple[str, bool]] = []
        self.db = _FakeDbHandle()

    def create_pending(self, *, founder_id, amount_inr, currency, gateway, gateway_order_id,
                       coupon_id=None, list_amount_inr=None, discount_inr=None, commit=True):
        pid = self._next_payment_id
        self._next_payment_id += 1
        self._payments[pid] = {
            "payment_id": pid, "founder_id": founder_id, "status": "pending",
            "gateway_order_id": gateway_order_id, "gateway_payment_id": None,
            "amount_inr": amount_inr, "subscription_id": None,
            "coupon_id": coupon_id, "list_amount_inr": list_amount_inr,
            "discount_inr": discount_inr,
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
                             amount_inr=row["amount_inr"], subscription_id=row["subscription_id"])


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
