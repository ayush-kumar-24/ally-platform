"""Paid trial + Razorpay autopay (app/payments/subscriptions.py).

Hand-written doubles, as in test_payments_service.py: the properties that
matter -- the right amounts reach Razorpay, nothing is granted before the
mandate is authorised, a charge never grants twice, a cancelled plan runs to
its period end and no further -- are asserted without Razorpay or a database.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.credits.models import CreditOperation
from app.payments.errors import (
    AutopayAlreadyActiveError,
    InvalidCheckoutCallbackError,
    NoAutopayError,
    PaymentNotFoundError,
    TrialAlreadyUsedError,
    TrialUnavailableError,
)
from app.payments.gateway import GatewaySubscription
from app.payments.models import SubscriptionRecord, WebhookOutcome
from app.payments.service import PaymentService
from app.payments.subscriptions import SubscriptionService
from app.plans.catalog import PLANS, TRIAL_DAYS, PlanTier

NOW = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
KEY_SECRET = "rzp_key_secret"
WEBHOOK_SECRET = "whsec_test"
IDS = {"basic": ("plan_basic", "offer_basic"), "starter": ("plan_plus", "offer_plus"),
       "pro": ("plan_pro", "offer_pro")}


class Clock:
    def __init__(self, at=NOW):
        self.at = at

    def __call__(self):
        return self.at


class FakeGateway:
    key_id = "rzp_test_key"

    def __init__(self):
        self.created = []
        self.cancelled = []
        self.subscriptions = {}
        self.payments = {}
        self.invoices = {}
        self._n = 0

    def create_subscription(self, **kwargs):
        self._n += 1
        sid = f"sub_{self._n}"
        self.created.append(kwargs)
        self.subscriptions[sid] = {"id": sid, "status": "created"}
        return GatewaySubscription(subscription_id=sid, status="created")

    def fetch_subscription(self, sid):
        return self.subscriptions[sid]

    def cancel_subscription(self, sid, *, at_cycle_end):
        self.cancelled.append((sid, at_cycle_end))
        return {"id": sid, "status": "cancelled"}

    def fetch_payment(self, pid):
        return self.payments[pid]

    def fetch_invoice(self, iid):
        return self.invoices[iid]

    def verify_subscription_checkout_signature(self, *, subscription_id, payment_id, signature):
        expected = hmac.new(KEY_SECRET.encode(), f"{payment_id}|{subscription_id}".encode(),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def verify_webhook_signature(self, *, body, signature):
        expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")


class FakeRepository:
    def __init__(self):
        self.subs: dict[int, dict] = {}
        self.payments: dict[str, dict] = {}
        self.plan_of: dict[int, str] = {}
        self.db = None

    # subscriptions
    def create_pending_subscription(self, *, founder_id, plan_type, amount_inr, billing_cycle,
                                    trial_ends_at, gateway_subscription_id):
        sid = len(self.subs) + 1
        self.subs[sid] = dict(subscription_id=sid, founder_id=founder_id, plan_type=plan_type,
                              status="pending", billing_cycle=billing_cycle,
                              amount_inr=amount_inr, trial_ends_at=trial_ends_at,
                              expires_at=None, cancelled_at=None,
                              gateway_subscription_id=gateway_subscription_id)
        return sid

    def _rec(self, d):
        return SubscriptionRecord(**d) if d else None

    def get_subscription_by_gateway_id(self, gsid):
        return self._rec(next((d for d in self.subs.values()
                               if d["gateway_subscription_id"] == gsid), None))

    def get_current_autopay(self, founder_id):
        rows = [d for d in self.subs.values()
                if d["founder_id"] == founder_id and d["status"] != "pending"]
        return self._rec(rows[-1] if rows else None)

    def has_used_trial(self, founder_id):
        return any(d["founder_id"] == founder_id and d["status"] != "pending"
                   for d in self.subs.values())

    def update_subscription(self, sid, *, status=None, billing_cycle=None, expires_at=None,
                            clear_expiry=False, cancelled_at=None, cancellation_reason=None):
        d = self.subs[sid]
        for k, v in (("status", status), ("billing_cycle", billing_cycle),
                     ("expires_at", expires_at), ("cancelled_at", cancelled_at)):
            if v is not None:
                d[k] = v
        if clear_expiry:
            d["expires_at"] = None

    def has_other_live_plan(self, founder_id, *, excluding_subscription_id, now):
        return False

    def find_lapsed_autopay(self, now):
        out = []
        for d in self.subs.values():
            r = self._rec(d)
            if (d["status"] in ("cancelled", "expired") and r.access_until is not None
                    and r.access_until <= now
                    and self.plan_of.get(d["founder_id"]) == d["plan_type"]):
                out.append(r)
        return out

    # payments + plan
    def get_by_gateway_payment_id(self, gpid):
        return self.payments.get(gpid)

    def record_subscription_payment(self, **kw):
        self.payments[kw["gateway_payment_id"]] = kw
        return len(self.payments)

    def grant_plan(self, founder_id, plan_type):
        self.plan_of[founder_id] = plan_type

    def revoke_plan(self, founder_id, plan_type):
        if self.plan_of.get(founder_id) != plan_type:
            return False
        self.plan_of[founder_id] = "free"
        return True


class FakeCredits:
    def __init__(self):
        self.adjustments = []

    def adjust(self, founder_id, *, admin_id, operation, amount, reason):
        self.adjustments.append((founder_id, operation, amount))


@pytest.fixture
def env():
    clock = Clock()
    gateway, repo, credits = FakeGateway(), FakeRepository(), FakeCredits()
    svc = SubscriptionService(gateway, repo, credits, trial_ids=IDS.get, clock=clock)
    return svc, gateway, repo, credits, clock


def _event(event, sid, payment=None, current_end=None):
    payload = {"subscription": {"entity": {"id": sid, "current_end": current_end}}}
    if payment:
        payload["payment"] = {"entity": payment}
    return {"event": event, "payload": payload}


def _pay(pid, rupees, at, status="captured"):
    return {"id": pid, "amount": rupees * 100, "status": status,
            "created_at": int(at.timestamp()), "order_id": f"order_{pid}"}


# --- catalog ------------------------------------------------------------------

def test_trial_prices_and_day_11_charges():
    assert [PLANS[t].trial_price_inr for t in (PlanTier.BASIC, PlanTier.STARTER, PlanTier.PRO)] \
        == [19, 49, 99]
    assert PLANS[PlanTier.PRO].first_charge_inr == 900
    assert PLANS[PlanTier.STARTER].first_charge_inr == 450
    assert PLANS[PlanTier.BASIC].first_charge_inr == 180
    assert TRIAL_DAYS == 10
    assert PLANS[PlanTier.PRO].trial_credits == 80
    assert PLANS[PlanTier.FREE].offers_trial is False


# --- starting a trial ----------------------------------------------------------

def test_start_trial_asks_razorpay_for_the_right_subscription(env):
    svc, gateway, repo, _, _ = env
    checkout = svc.start_trial(7, PlanTier.PRO)

    sent = gateway.created[0]
    assert sent["plan_id"] == "plan_pro" and sent["offer_id"] == "offer_pro"
    assert sent["upfront_amount_paise"] == 9_900
    assert sent["start_at"] == int((NOW + timedelta(days=10)).timestamp())
    assert sent["total_count"] > 1
    assert checkout.first_charge_paise == 90_000 and checkout.recurring is True
    # Nothing granted until the mandate is authorised.
    assert repo.subs[1]["status"] == "pending" and repo.plan_of == {}


def test_starter_trial_charges_once(env):
    svc, gateway, repo, _, _ = env
    checkout = svc.start_trial(7, PlanTier.BASIC)
    assert gateway.created[0]["total_count"] == 1
    assert checkout.recurring is False and checkout.first_charge_paise == 18_000
    assert repo.subs[1]["billing_cycle"] == "one_time"


def test_trial_refused_when_razorpay_ids_missing(env):
    _, gateway, repo, credits, clock = env
    svc = SubscriptionService(gateway, repo, credits, trial_ids=lambda t: None, clock=clock)
    with pytest.raises(TrialUnavailableError):
        svc.start_trial(7, PlanTier.PRO)
    assert gateway.created == []


def test_one_trial_per_founder(env):
    svc, gateway, repo, _, _ = env
    svc.start_trial(7, PlanTier.PRO)
    svc.handle_event("subscription.authenticated", _event("subscription.authenticated", "sub_1"))
    with pytest.raises(TrialAlreadyUsedError):
        svc.start_trial(7, PlanTier.STARTER)


def test_abandoned_checkout_does_not_use_up_the_trial(env):
    svc, _, _, _, _ = env
    svc.start_trial(7, PlanTier.PRO)        # never authorised
    svc.start_trial(7, PlanTier.PRO)        # allowed


def test_autopay_already_active_blocks_a_second(env):
    svc, _, repo, _, _ = env
    repo.has_used_trial = lambda fid: False
    svc.start_trial(7, PlanTier.PRO)
    svc.handle_event("subscription.authenticated", _event("subscription.authenticated", "sub_1"))
    with pytest.raises(AutopayAlreadyActiveError):
        svc.start_trial(7, PlanTier.STARTER)


# --- activation --------------------------------------------------------------

def test_authenticated_starts_the_trial_once(env):
    svc, _, repo, credits, _ = env
    svc.start_trial(7, PlanTier.PRO)
    fee = _pay("pay_fee", 99, NOW)
    first = svc.handle_event("subscription.authenticated",
                             _event("subscription.authenticated", "sub_1", fee))
    again = svc.handle_event("subscription.authenticated",
                             _event("subscription.authenticated", "sub_1", fee))

    assert first.outcome == WebhookOutcome.TRIAL_STARTED
    assert again.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.plan_of[7] == "pro" and repo.subs[1]["status"] == "trial"
    assert credits.adjustments == [(7, CreditOperation.ADD, 80)]
    assert repo.payments["pay_fee"]["amount_inr"] == 99


def test_confirm_trial_checks_signature_and_ownership(env):
    svc, gateway, repo, _, _ = env
    svc.start_trial(7, PlanTier.PRO)
    gateway.subscriptions["sub_1"]["status"] = "authenticated"
    gateway.payments["pay_fee"] = _pay("pay_fee", 99, NOW)

    with pytest.raises(PaymentNotFoundError):
        svc.confirm_trial(8, gateway_subscription_id="sub_1", gateway_payment_id="pay_fee")
    with pytest.raises(InvalidCheckoutCallbackError):
        svc.confirm_trial(7, gateway_subscription_id="sub_1", gateway_payment_id="pay_fee",
                          signature="forged")

    good = hmac.new(KEY_SECRET.encode(), b"pay_fee|sub_1", hashlib.sha256).hexdigest()
    result = svc.confirm_trial(7, gateway_subscription_id="sub_1", gateway_payment_id="pay_fee",
                               signature=good)
    assert result.outcome == WebhookOutcome.TRIAL_STARTED
    assert "pay_fee" in repo.payments


def test_confirm_before_authorisation_grants_nothing(env):
    svc, _, repo, _, _ = env
    svc.start_trial(7, PlanTier.PRO)
    result = svc.confirm_trial(7, gateway_subscription_id="sub_1", gateway_payment_id="pay_x")
    assert result.outcome == WebhookOutcome.NOT_CAPTURED and repo.plan_of == {}


# --- day 11 and after ----------------------------------------------------------

def _trialing(env, tier=PlanTier.PRO):
    svc, _, _, _, clock = env
    svc.start_trial(7, tier)
    svc.handle_event("subscription.authenticated",
                     _event("subscription.authenticated", "sub_1", _pay("pay_fee", 99, NOW)))
    clock.at = NOW + timedelta(days=10, minutes=5)


def test_day_11_charge_renews_and_grants_monthly_credits_once(env):
    svc, _, repo, credits, clock = env
    _trialing(env)
    period_end = NOW + timedelta(days=40)
    charge = _pay("pay_d11", 900, clock.at)
    first = svc.handle_event("subscription.charged", _event(
        "subscription.charged", "sub_1", charge, int(period_end.timestamp())))
    again = svc.handle_event("subscription.charged", _event(
        "subscription.charged", "sub_1", charge, int(period_end.timestamp())))

    assert first.outcome == WebhookOutcome.RENEWED
    assert again.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.subs[1]["status"] == "active" and repo.subs[1]["expires_at"] == period_end
    assert credits.adjustments[-1] == (7, CreditOperation.ADD, 240)
    assert sum(1 for a in credits.adjustments if a[2] == 240) == 1


def test_invoice_payment_then_charged_event_grants_once(env):
    svc, gateway, repo, credits, clock = env
    _trialing(env)
    charge = {**_pay("pay_d11", 900, clock.at), "invoice_id": "inv_1"}
    gateway.invoices["inv_1"] = {"id": "inv_1", "subscription_id": "sub_1"}

    assert svc.handle_invoice_payment(charge).outcome == WebhookOutcome.RENEWED
    late = svc.handle_event("subscription.charged",
                            _event("subscription.charged", "sub_1", charge))
    assert late.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert sum(1 for a in credits.adjustments if a[2] == 240) == 1


def test_trial_fee_payment_arriving_late_is_not_a_renewal(env):
    svc, gateway, repo, credits, clock = env
    svc.start_trial(7, PlanTier.PRO)
    svc.handle_event("subscription.authenticated", _event("subscription.authenticated", "sub_1"))
    clock.at = NOW + timedelta(minutes=2)
    fee = {**_pay("pay_fee", 99, NOW), "invoice_id": "inv_0"}
    gateway.invoices["inv_0"] = {"id": "inv_0", "subscription_id": "sub_1"}

    result = svc.handle_invoice_payment(fee)
    assert result.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.subs[1]["status"] == "trial"
    assert repo.payments["pay_fee"]["amount_inr"] == 99


def test_starter_day_11_charge_has_no_expiry_and_completion_keeps_it(env):
    svc, _, repo, _, clock = env
    _trialing(env, PlanTier.BASIC)
    svc.handle_event("subscription.charged", _event(
        "subscription.charged", "sub_1", _pay("pay_d11", 180, clock.at)))
    svc.handle_event("subscription.completed", _event("subscription.completed", "sub_1"))
    assert repo.subs[1]["status"] == "active" and repo.subs[1]["expires_at"] is None
    assert repo.plan_of[7] == "basic"
    assert svc.status(7)["can_cancel"] is False


def test_halted_revokes_the_plan(env):
    svc, _, repo, _, _ = env
    _trialing(env)
    result = svc.handle_event("subscription.halted", _event("subscription.halted", "sub_1"))
    assert result.outcome == WebhookOutcome.EXPIRED
    assert repo.plan_of[7] == "free" and repo.subs[1]["status"] == "expired"


# --- cancelling ----------------------------------------------------------------

def test_cancel_in_trial_stops_autopay_now_but_keeps_access_to_trial_end(env):
    svc, gateway, repo, _, clock = env
    svc.start_trial(7, PlanTier.PRO)
    svc.handle_event("subscription.authenticated", _event("subscription.authenticated", "sub_1"))
    clock.at = NOW + timedelta(days=3)

    status = svc.cancel(7)
    assert gateway.cancelled == [("sub_1", False)]
    assert status["status"] == "cancelled" and status["next_charge_inr"] is None
    assert svc.expire_lapsed() == {"checked": 0, "revoked": 0}
    assert repo.plan_of[7] == "pro"

    clock.at = NOW + timedelta(days=10, seconds=1)
    assert svc.expire_lapsed() == {"checked": 1, "revoked": 1}
    assert repo.plan_of[7] == "free"
    assert svc.expire_lapsed() == {"checked": 0, "revoked": 0}


def test_cancel_when_paid_runs_to_cycle_end(env):
    svc, gateway, repo, _, clock = env
    _trialing(env)
    svc.handle_event("subscription.charged", _event(
        "subscription.charged", "sub_1", _pay("pay_d11", 900, clock.at)))
    svc.cancel(7)
    assert gateway.cancelled == [("sub_1", True)]
    assert repo.plan_of[7] == "pro"


def test_cancel_without_autopay(env):
    svc, _, _, _, _ = env
    with pytest.raises(NoAutopayError):
        svc.cancel(7)


def test_status_reports_the_day_11_charge(env):
    svc, _, _, _, _ = env
    svc.start_trial(7, PlanTier.PRO)
    assert svc.status(7) is None          # pending is not a plan yet
    svc.handle_event("subscription.authenticated", _event("subscription.authenticated", "sub_1"))
    st = svc.status(7)
    assert st["status"] == "trial" and st["next_charge_inr"] == 900
    assert st["next_charge_at"] == NOW + timedelta(days=10)


# --- routing through PaymentService.handle_webhook ------------------------------

def test_signed_subscription_webhook_is_routed():
    gateway, repo, credits = FakeGateway(), FakeRepository(), FakeCredits()
    service = PaymentService(gateway, repo, credits, clock=Clock())
    service.subscriptions = lambda: SubscriptionService(
        gateway, repo, credits, trial_ids=IDS.get, clock=Clock())
    service.subscriptions().start_trial(7, PlanTier.STARTER)

    body = json.dumps(_event("subscription.authenticated", "sub_1")).encode()
    sig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    result = service.handle_webhook(body=body, signature=sig)
    assert result.outcome == WebhookOutcome.TRIAL_STARTED
    assert repo.plan_of[7] == "starter"
    assert credits.adjustments == [(7, CreditOperation.ADD, 35)]
