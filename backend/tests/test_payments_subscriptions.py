"""SubscriptionService -- the recurring tiers, and the properties that make
them safe.

The one rule these tests exist to hold: ACCESS IS GRANTED BY MONEY ARRIVING
AND BY NOTHING ELSE. A subscription that exists grants nothing, a mandate the
founder authorised grants nothing, and `subscription.activated` grants
nothing. Only `subscription.charged` -- Razorpay saying it took the money --
moves a founder onto a plan.

Everything here is a hand-written double, the same way test_payments_service.py
does it: no live Razorpay account and no database, so the assertions are about
behaviour rather than about plumbing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.credits.models import CreditOperation
from app.payments.errors import (
    InvalidCheckoutError,
    NoActiveSubscriptionError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
    SubscriptionAlreadyActiveError,
    SubscriptionPlanNotConfiguredError,
)
from app.payments.gateway import GatewaySubscription, PaymentGatewayError
from app.payments.models import WebhookOutcome
from app.payments.subscription_repository import SubscriptionRecord
from app.payments.subscriptions import SubscriptionService
from app.plans.catalog import PLANS, PlanTier

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
PERIOD_END = NOW + timedelta(days=30)
GRACE_DAYS = 5


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


# --- fakes ------------------------------------------------------------------

class FakeGateway:
    def __init__(self, *, subscription_id="sub_1", raise_on_create=None,
                 raise_on_cancel=None, remote=None, cancel_response=None):
        self.key_id = "rzp_test_key"
        self.subscription_id = subscription_id
        self.raise_on_create = raise_on_create
        self.raise_on_cancel = raise_on_cancel
        self.remote = remote or {}
        self.cancel_response = cancel_response
        self.created = []
        self.cancelled = []

    def create_subscription(self, *, plan_id, total_count, notes, customer_notify=True):
        if self.raise_on_create:
            raise self.raise_on_create
        self.created.append({"plan_id": plan_id, "total_count": total_count, "notes": notes,
                             "customer_notify": customer_notify})
        return GatewaySubscription(subscription_id=self.subscription_id, status="created",
                                   plan_id=plan_id)

    def cancel_subscription(self, subscription_id, *, at_cycle_end):
        if self.raise_on_cancel:
            raise self.raise_on_cancel
        self.cancelled.append((subscription_id, at_cycle_end))
        return self.cancel_response or {
            "id": subscription_id, "status": "active" if at_cycle_end else "cancelled",
            "cancel_at_cycle_end": 1 if at_cycle_end else 0,
            "current_end": _epoch(PERIOD_END),
        }

    def fetch_subscription(self, subscription_id):
        """Answers PER ID, like the real one. A double that returns the same
        entity for every id hides a whole class of bug -- it did here, and is
        why reconcile now checks that the entity it got back is the one it
        asked about."""
        return self.remote.get(subscription_id, {"id": subscription_id, "status": "halted"})


class FakeSubscriptionRepository:
    def __init__(self, plan_ids=None):
        self._rows: dict[int, dict] = {}
        self._by_gateway: dict[str, int] = {}
        self._next_id = 1
        self._plan_ids = plan_ids if plan_ids is not None else {("starter", "test"): "plan_PLUS",
                                                                ("pro", "test"): "plan_PRO"}
        self.payments_recorded: list[dict] = []
        self.invoices: list[dict] = []
        self.db = _FakeDb()

    # plan map
    def active_plan_id(self, tier, mode):
        return self._plan_ids.get((tier, mode))

    # subscriptions
    def create_pending(self, *, founder_id, plan_type, amount_inr, gateway_subscription_id,
                       razorpay_plan_id, status, gateway="razorpay"):
        sid = self._next_id
        self._next_id += 1
        self._rows[sid] = {
            "subscription_id": sid, "founder_id": founder_id, "plan_type": plan_type,
            "status": status, "gateway_subscription_id": gateway_subscription_id,
            "razorpay_plan_id": razorpay_plan_id, "amount_inr": amount_inr, "paid_count": 0,
            "current_period_start": None, "current_period_end": None, "next_charge_at": None,
            "access_until": None, "cancel_at_period_end": False, "cancelled_at": None,
            "ended_at": None, "activated_at": None, "started_at": NOW,
            "billing_cycle": "monthly",
        }
        self._by_gateway[gateway_subscription_id] = sid
        return sid

    def get_by_gateway_id(self, gateway_subscription_id):
        sid = self._by_gateway.get(gateway_subscription_id)
        return _record(self._rows[sid]) if sid else None

    def get_by_id(self, subscription_id):
        row = self._rows.get(subscription_id)
        return _record(row) if row else None

    def live_for_founder(self, founder_id):
        live = ("created", "authenticated", "active", "pending", "halted")
        for row in sorted(self._rows.values(), key=lambda r: -r["subscription_id"]):
            if row["founder_id"] == founder_id and row["status"] in live:
                return _record(row)
        return None

    def latest_for_founder(self, founder_id):
        for row in sorted(self._rows.values(), key=lambda r: -r["subscription_id"]):
            if row["founder_id"] == founder_id:
                return _record(row)
        return None

    def sync_from_entity(self, subscription_id, *, commit=True, **fields):
        row = self._rows[subscription_id]
        for key, value in fields.items():
            if value is not None:          # COALESCE: None means "leave alone"
                row[key] = value

    def set_access_until(self, subscription_id, access_until, *, commit=True):
        self._rows[subscription_id]["access_until"] = access_until

    def mark_expired(self, subscription_id, *, at):
        # Deliberately does NOT commit, exactly like the real one: the caller's
        # grant_plan is what commits both together, and a failure in between
        # must undo this.
        row = self._rows[subscription_id]
        before = (row["status"], row["ended_at"])
        row["status"] = "expired"
        row["ended_at"] = at

        def undo():
            row["status"], row["ended_at"] = before

        self.db.on_rollback(undo)

    def find_lapsed(self, *, now, limit=200):
        return [_record(r) for r in self._rows.values()
                if r["access_until"] and r["access_until"] < now and r["status"] != "expired"]

    # payments / invoices
    def record_subscription_payment(self, *, gateway_payment_id, commit=True, **fields):
        if any(p["gateway_payment_id"] == gateway_payment_id for p in self.payments_recorded):
            return None                    # the unique index refusing a redelivery
        self.payments_recorded.append({"gateway_payment_id": gateway_payment_id, **fields})
        return len(self.payments_recorded)

    def upsert_invoice(self, *, gateway_invoice_id, commit=True, **fields):
        for inv in self.invoices:
            if inv["gateway_invoice_id"] == gateway_invoice_id:
                inv.update(fields)
                return self.invoices.index(inv) + 1
        self.invoices.append({"gateway_invoice_id": gateway_invoice_id, **fields})
        return len(self.invoices)


class _FakeDb:
    """Models the transaction boundary, not just the call count.

    Uncommitted writes register an undo, `commit()` makes them permanent and
    `rollback()` reverses them -- which is what the real Session does and what
    several of these tests are actually asserting. A double that only counted
    commits would let a "these two writes are one transaction" claim pass while
    being false in production, which is the one thing it must not do.
    """

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.executed = []
        self._undo = []

    def on_rollback(self, undo):
        self._undo.append(undo)

    def commit(self):
        self.commits += 1
        self._undo.clear()

    def rollback(self):
        self.rollbacks += 1
        for undo in reversed(self._undo):
            undo()
        self._undo.clear()

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        return self


class FakePaymentRepository:
    def __init__(self, db=None):
        self.plans_granted = []
        self._by_order = {}
        #: Shared with the subscription repository where a test needs the two
        #: to be one transaction -- which is how the real container wires them.
        self.db = db

    def grant_plan(self, founder_id, plan_type):
        self.plans_granted.append((founder_id, plan_type))
        if self.db is not None:
            self.db.commit()      # the real PaymentRepository.grant_plan commits

    def get_by_gateway_order_id(self, order_id):
        return self._by_order.get(order_id)


class FakeCredits:
    def __init__(self, raise_on_adjust=None):
        self.grants = []
        self.raise_on_adjust = raise_on_adjust

    def adjust(self, founder_id, *, admin_id, operation, amount, reason):
        if self.raise_on_adjust:
            raise self.raise_on_adjust
        self.grants.append({"founder_id": founder_id, "admin_id": admin_id,
                            "operation": operation, "amount": amount, "reason": reason})


def _record(row) -> SubscriptionRecord:
    return SubscriptionRecord(**{k: v for k, v in row.items()})


@pytest.fixture(autouse=True)
def _test_mode(monkeypatch):
    """Every test runs as a test-mode backend. `razorpay_mode` is derived from
    the key id, so this is also the guard that the derivation works at all."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_abc", raising=False)
    monkeypatch.setattr(settings, "SUBSCRIPTION_GRACE_DAYS", GRACE_DAYS, raising=False)
    monkeypatch.setattr(settings, "RAZORPAY_SUBSCRIPTION_TOTAL_COUNT", 120, raising=False)


#: Distinguishes "use the default fake gateway" from "there is no gateway",
#: which is the whole point of the unconfigured test -- `gateway=None` has to
#: reach the service as None.
_DEFAULT = object()


def _service(gateway=_DEFAULT, repo=None, payments=None, credits=None):
    gateway = FakeGateway() if gateway is _DEFAULT else gateway
    repo = repo or FakeSubscriptionRepository()
    payments = payments or FakePaymentRepository()
    credits = credits or FakeCredits()
    return (SubscriptionService(gateway, repo, payments, credits, clock=lambda: NOW),
            repo, payments, credits)


def _charged(*, subscription_id="sub_1", payment_id="pay_1", paid_count=1,
             amount=49900, period_end=PERIOD_END, invoice_id="inv_1"):
    return {"payload": {
        "subscription": {"entity": {
            "id": subscription_id, "status": "active", "paid_count": paid_count,
            "current_start": _epoch(NOW), "current_end": _epoch(period_end),
            "charge_at": _epoch(period_end)}},
        "payment": {"entity": {
            "id": payment_id, "order_id": "order_1", "amount": amount,
            "currency": "INR", "invoice_id": invoice_id}}}}


def _sub_event(status, *, subscription_id="sub_1", **extra):
    return {"payload": {"subscription": {"entity": {
        "id": subscription_id, "status": status, **extra}}}}


# --- start_subscription -----------------------------------------------------

def test_unconfigured_gateway_refuses():
    service, *_ = _service(gateway=None)
    with pytest.raises(PaymentsNotConfiguredError):
        service.start_subscription(1, PlanTier.STARTER)


def test_a_one_time_tier_cannot_be_subscribed_to():
    """Starter is Rs 199 paid ONCE for one diagnosis. A monthly mandate for it
    would charge a founder every month for something they already have -- the
    guide says so in as many words, and it is worth a hard refusal."""
    service, *_ = _service()
    with pytest.raises(InvalidCheckoutError):
        service.start_subscription(1, PlanTier.BASIC)


def test_the_free_plan_cannot_be_subscribed_to():
    service, *_ = _service()
    with pytest.raises(InvalidCheckoutError):
        service.start_subscription(1, PlanTier.FREE)


def test_no_registered_plan_id_refuses_rather_than_guessing():
    """503, not a subscription against an invented plan id. What a founder is
    charged every month is decided by the Razorpay Plan, and guessing one
    charges an amount nobody chose."""
    service, *_ = _service(repo=FakeSubscriptionRepository(plan_ids={}))
    with pytest.raises(SubscriptionPlanNotConfiguredError):
        service.start_subscription(1, PlanTier.STARTER)


def test_the_plan_id_is_chosen_by_tier_and_mode_not_by_the_caller():
    gateway = FakeGateway()
    service, *_ = _service(gateway=gateway)
    service.start_subscription(42, PlanTier.PRO)
    assert gateway.created[0]["plan_id"] == "plan_PRO"
    assert gateway.created[0]["notes"] == {"founder_id": "42", "plan_tier": "pro"}


def test_starting_a_subscription_grants_nothing():
    """THE CENTRAL PROPERTY. The row exists so the webhook has something to
    attach to; it carries no access clock and no plan grant, and the founder is
    on whatever they were on before."""
    service, repo, payments, credits = _service()
    session = service.start_subscription(42, PlanTier.STARTER)

    record = repo.get_by_gateway_id("sub_1")
    assert record.status == "created"
    assert record.access_until is None
    assert record.paid_count == 0
    assert payments.plans_granted == []
    assert credits.grants == []
    assert session.amount_inr == PLANS[PlanTier.STARTER].price_inr
    assert session.plan_name == PLANS[PlanTier.STARTER].name


def test_a_second_subscription_is_refused_while_one_is_live():
    """Two live mandates means two charges a month, and the founder would find
    out on their card statement."""
    service, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    with pytest.raises(SubscriptionAlreadyActiveError):
        service.start_subscription(42, PlanTier.PRO)


def test_a_gateway_failure_is_a_502_and_leaves_no_subscription_row():
    gateway = FakeGateway(raise_on_create=PaymentGatewayError("nope", status_code=400))
    service, repo, *_ = _service(gateway=gateway)
    with pytest.raises(PaymentGatewayUnavailableError):
        service.start_subscription(42, PlanTier.STARTER)
    assert repo.live_for_founder(42) is None


# --- subscription.charged: the one grant ------------------------------------

def test_a_charge_grants_the_plan_credits_and_an_access_clock():
    service, repo, payments, credits = _service()
    service.start_subscription(42, PlanTier.STARTER)

    result = service.handle_event("subscription.charged", _charged())

    assert result.outcome == WebhookOutcome.CAPTURED
    assert payments.plans_granted == [(42, "starter")]
    assert credits.grants[0]["operation"] == CreditOperation.ADD
    assert credits.grants[0]["amount"] == PLANS[PlanTier.STARTER].monthly_credits

    record = repo.get_by_gateway_id("sub_1")
    assert record.status == "active"
    assert record.paid_count == 1
    assert record.current_period_end == PERIOD_END
    # THE ACCESS CLOCK: the period paid for, plus the grace window. That single
    # value is the whole failed-payment policy -- a renewal that fails leaves
    # time on the clock while Razorpay retries.
    assert record.access_until == PERIOD_END + timedelta(days=GRACE_DAYS)


def test_the_charged_payment_is_recorded_against_the_subscription():
    service, repo, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    payment = repo.payments_recorded[0]
    assert payment["gateway_payment_id"] == "pay_1"
    assert payment["gateway_subscription_id"] == "sub_1"
    assert payment["gateway_invoice_id"] == "inv_1"
    assert payment["plan_tier"] == "starter"
    # Paise in, rupees out -- one conversion, so `payments.amount_inr` and the
    # admin revenue views cannot be out by a factor of 100.
    assert payment["amount_inr"] == 499


def test_a_redelivered_charge_grants_nothing_twice():
    """Razorpay retries deliveries. A month of credits and a plan grant must
    apply exactly once per charge."""
    service, repo, payments, credits = _service()
    service.start_subscription(42, PlanTier.STARTER)

    first = service.handle_event("subscription.charged", _charged())
    second = service.handle_event("subscription.charged", _charged())

    assert first.outcome == WebhookOutcome.CAPTURED
    assert second.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert payments.plans_granted == [(42, "starter")]
    assert len(credits.grants) == 1
    assert len(repo.payments_recorded) == 1


def test_a_renewal_moves_the_clock_forward():
    service, repo, payments, credits = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    next_end = PERIOD_END + timedelta(days=30)
    service.handle_event("subscription.charged",
                         _charged(payment_id="pay_2", paid_count=2, period_end=next_end))

    record = repo.get_by_gateway_id("sub_1")
    assert record.paid_count == 2
    assert record.access_until == next_end + timedelta(days=GRACE_DAYS)
    assert len(credits.grants) == 2          # a month of credits per month paid


def test_a_charge_for_an_unknown_subscription_grants_nothing():
    """Never act on an entity that arrived from nowhere -- the same refusal the
    one-time path makes for an unknown order."""
    service, _, payments, _ = _service()
    result = service.handle_event("subscription.charged", _charged())
    assert result.outcome == WebhookOutcome.UNKNOWN_PAYMENT
    assert payments.plans_granted == []


def test_a_charge_with_no_payment_entity_grants_nothing():
    """`subscription.charged` that names no money is not something to guess at."""
    service, _, payments, _ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    event = _charged()
    event["payload"].pop("payment")
    result = service.handle_event("subscription.charged", event)
    assert result.outcome == WebhookOutcome.UNKNOWN_PAYMENT
    assert payments.plans_granted == []


def test_a_credit_grant_failure_does_not_undo_the_plan_grant():
    """The founder paid and has their plan. A bookkeeping failure must not roll
    that back, or fail the webhook and make Razorpay retry a charge that
    succeeded."""
    credits = FakeCredits(raise_on_adjust=RuntimeError("credits down"))
    service, repo, payments, _ = _service(credits=credits)
    service.start_subscription(42, PlanTier.STARTER)

    result = service.handle_event("subscription.charged", _charged())

    assert result.outcome == WebhookOutcome.CAPTURED
    assert payments.plans_granted == [(42, "starter")]
    assert repo.get_by_gateway_id("sub_1").access_until is not None


# --- the events that grant NOTHING ------------------------------------------

@pytest.mark.parametrize("event", ["subscription.authenticated", "subscription.activated",
                                   "subscription.updated"])
def test_state_events_mirror_without_granting(event):
    """`activated` is the tempting one: Razorpay marks a subscription active
    around its first charge. It still grants nothing here, because the event
    that names the money is `subscription.charged` and keeping ONE grant path
    is what makes double-granting impossible to reintroduce."""
    service, repo, payments, credits = _service()
    service.start_subscription(42, PlanTier.STARTER)

    result = service.handle_event(event, _sub_event("authenticated"))

    assert result.outcome == WebhookOutcome.STATE_SYNCED
    assert payments.plans_granted == []
    assert credits.grants == []
    assert repo.get_by_gateway_id("sub_1").access_until is None


def test_a_pending_renewal_keeps_access():
    """A failed charge Razorpay is still retrying. The founder has grace time
    on the clock from their last successful charge, and this must not touch
    it -- guide step 12: the retry schedule is Razorpay's, not ours."""
    service, repo, payments, _ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())
    before = repo.get_by_gateway_id("sub_1").access_until

    result = service.handle_event("subscription.pending", _sub_event("pending"))

    assert result.outcome == WebhookOutcome.FAILED_RECORDED
    assert repo.get_by_gateway_id("sub_1").status == "pending"
    assert repo.get_by_gateway_id("sub_1").access_until == before
    assert payments.plans_granted == [(42, "starter")]      # still on the plan


def test_halting_ends_the_grace_window_now():
    """Razorpay has given up retrying. This is the one place access is
    SHORTENED -- the founder has had their retries and their grace days, and no
    further money is coming."""
    service, repo, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    service.handle_event("subscription.halted", _sub_event("halted"))

    record = repo.get_by_gateway_id("sub_1")
    assert record.status == "halted"
    assert record.access_until == NOW


def test_cancelling_keeps_the_period_already_paid_for():
    service, repo, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    result = service.handle_event(
        "subscription.cancelled", _sub_event("cancelled", current_end=_epoch(PERIOD_END)))

    record = repo.get_by_gateway_id("sub_1")
    assert result.outcome == WebhookOutcome.SUBSCRIPTION_ENDED
    assert record.status == "cancelled"
    # The period, NOT period + grace: a cancellation must not hand out the
    # grace days a successful charge would have.
    assert record.access_until == PERIOD_END


def test_cancelling_never_extends_access():
    """A `current_end` further out than what the founder already has must not
    become a longer entitlement."""
    service, repo, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())
    repo.set_access_until(1, NOW + timedelta(days=2))

    service.handle_event("subscription.cancelled",
                         _sub_event("cancelled", current_end=_epoch(PERIOD_END)))

    assert repo.get_by_gateway_id("sub_1").access_until == NOW + timedelta(days=2)


def test_an_unrelated_event_is_ignored_not_errored():
    service, *_ = _service()
    result = service.handle_event("subscription.some.future.thing", _sub_event("active"))
    assert result.outcome == WebhookOutcome.IGNORED_EVENT


# --- invoices ---------------------------------------------------------------

def test_invoice_paid_is_recorded_against_the_founder():
    service, repo, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)

    result = service.handle_event("invoice.paid", {"payload": {"invoice": {"entity": {
        "id": "inv_1", "subscription_id": "sub_1", "order_id": "order_1",
        "payment_id": "pay_1", "amount": 49900, "status": "paid",
        "short_url": "https://rzp.io/i/abc", "invoice_number": "INV-001",
        "paid_at": _epoch(NOW)}}}})

    assert result.outcome == WebhookOutcome.INVOICE_RECORDED
    invoice = repo.invoices[0]
    assert invoice["founder_id"] == 42
    assert invoice["total_amount_inr"] == 499
    assert invoice["invoice_url"] == "https://rzp.io/i/abc"
    # No tax number is invented when Razorpay reported none -- see guide step 14.
    assert invoice["tax_amount_inr"] is None


def test_a_redelivered_invoice_does_not_duplicate_the_receipt():
    service, repo, *_ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    event = {"payload": {"invoice": {"entity": {
        "id": "inv_1", "subscription_id": "sub_1", "amount": 49900, "status": "paid"}}}}

    service.handle_event("invoice.paid", event)
    service.handle_event("invoice.paid", event)

    assert len(repo.invoices) == 1


def test_an_invoice_for_an_unknown_founder_is_not_stored():
    service, repo, *_ = _service()
    result = service.handle_event("invoice.paid", {"payload": {"invoice": {"entity": {
        "id": "inv_x", "subscription_id": "sub_nope", "amount": 49900, "status": "paid"}}}})
    assert result.outcome == WebhookOutcome.UNKNOWN_PAYMENT
    assert repo.invoices == []


# --- cancel -----------------------------------------------------------------

def test_cancel_with_no_subscription_is_a_404():
    service, *_ = _service()
    with pytest.raises(NoActiveSubscriptionError):
        service.cancel(42)


def test_cancel_defaults_to_period_end_and_reports_the_real_date():
    """The date this returns is what the confirmation screen shows the founder
    BEFORE they confirm. It has to be real."""
    gateway = FakeGateway()
    service, repo, *_ = _service(gateway=gateway)
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    result = service.cancel(42, reason="too expensive")

    assert gateway.cancelled == [("sub_1", True)]
    assert result.cancel_at_period_end is True
    assert result.access_until == PERIOD_END
    assert repo.get_by_gateway_id("sub_1").access_until == PERIOD_END


def test_cancel_now_ends_access_now():
    gateway = FakeGateway(cancel_response={"id": "sub_1", "status": "cancelled",
                                           "cancel_at_cycle_end": 0})
    service, repo, *_ = _service(gateway=gateway)
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    result = service.cancel(42, at_period_end=False)

    assert gateway.cancelled == [("sub_1", False)]
    assert result.cancel_at_period_end is False
    assert result.access_until == NOW


def test_cancel_believes_the_gateway_over_what_we_asked_for():
    """We asked for period-end; Razorpay says it cancelled immediately. The
    founder's access date must reflect what actually happened."""
    gateway = FakeGateway(cancel_response={"id": "sub_1", "status": "cancelled",
                                           "cancel_at_cycle_end": 0})
    service, *_ = _service(gateway=gateway)
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())

    result = service.cancel(42, at_period_end=True)

    assert result.cancel_at_period_end is False
    assert result.access_until == NOW


def test_a_gateway_failure_during_cancel_is_a_502():
    """And leaves the subscription alone. A cancellation that failed at
    Razorpay but succeeded here would stop the founder's access while the
    charges kept coming."""
    gateway = FakeGateway(raise_on_cancel=PaymentGatewayError("down", status_code=503))
    service, repo, *_ = _service(gateway=gateway)
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())
    before = repo.get_by_gateway_id("sub_1")

    with pytest.raises(PaymentGatewayUnavailableError):
        service.cancel(42)

    after = repo.get_by_gateway_id("sub_1")
    assert after.status == before.status
    assert after.access_until == before.access_until
    assert after.cancelled_at is None


# --- reconcile ---------------------------------------------------------------

def test_reconcile_recovers_a_charge_whose_webhook_was_lost():
    service, repo, payments, _ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.handle_event("subscription.charged", _charged())
    payments.plans_granted.clear()

    later_end = PERIOD_END + timedelta(days=30)
    service.gateway.remote["sub_1"] = {
        "id": "sub_1", "status": "active", "paid_count": 2,
        "current_start": _epoch(PERIOD_END), "current_end": _epoch(later_end)}

    assert service.reconcile(repo.get_by_gateway_id("sub_1")) is True
    record = repo.get_by_gateway_id("sub_1")
    assert record.paid_count == 2
    assert record.access_until == later_end + timedelta(days=GRACE_DAYS)
    assert payments.plans_granted == [(42, "starter")]


def test_reconcile_refuses_an_entity_for_a_different_subscription():
    """A correct gateway cannot return a mismatch -- which is exactly why the
    check costs nothing. Without it, one founder's paid month could be granted
    to another."""
    service, repo, payments, _ = _service()
    service.start_subscription(42, PlanTier.STARTER)
    service.gateway.remote["sub_1"] = {
        "id": "sub_SOMEONE_ELSE", "status": "active", "paid_count": 9,
        "current_end": _epoch(PERIOD_END)}

    assert service.reconcile(repo.get_by_gateway_id("sub_1")) is False
    assert payments.plans_granted == []


def test_reconcile_survives_a_gateway_outage():
    """Returns False rather than raising: the sweep that calls this must not
    die because Razorpay is briefly unreachable."""
    gateway = FakeGateway()
    gateway.fetch_subscription = lambda sid: (_ for _ in ()).throw(
        PaymentGatewayError("down", status_code=503))
    service, repo, *_ = _service(gateway=gateway)
    service.start_subscription(42, PlanTier.STARTER)
    assert service.reconcile(repo.get_by_gateway_id("sub_1")) is False
