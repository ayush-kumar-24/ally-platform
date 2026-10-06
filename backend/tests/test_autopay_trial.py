"""Autopay trial subscriptions -- the ₹11-then-₹999/month offer.

Hand-written fakes, same approach as test_payments_service.py: a fake Razorpay
and an in-memory repository, so these assert the money-safety properties
directly -- the right amounts go to Razorpay, access is granted only on
Razorpay's word, never twice, and taken away when (and only when) paid-for
access is over.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.coupons.errors import (
    CouponFullyRedeemedError,
    CouponNotTrialError,
    CouponStartsTrialError,
)
from app.coupons.models import Coupon, DiscountType
from app.coupons.service import CouponService
from app.payments.errors import InvalidCheckoutCallbackError
from app.payments.models import WebhookOutcome
from app.payments.subscription_repository import AutopaySubscription
from app.payments.subscriptions import (
    RENEWAL_GRACE,
    AutopayAlreadyActiveError,
    NoAutopaySubscriptionError,
    SubscriptionService,
)
from app.plans.catalog import PLANS, PlanTier

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
KEY_SECRET = "rzp_key_secret"
PRO = PLANS[PlanTier.PRO]


# --- fakes ------------------------------------------------------------------

def trial_coupon(**over) -> Coupon:
    base = dict(coupon_id=7, code="100FOUNDERS", description="Founding 100",
                discount_type=DiscountType.FIXED, discount_value=PRO.price_inr - 11,
                applies_to=["pro"], max_redemptions=100, max_per_founder=1,
                valid_from=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=25),
                is_active=True, trial_days=7)
    base.update(over)
    return Coupon(**base)


class FakeCouponRepo:
    def __init__(self, coupon, *, live=0):
        self.coupon, self.live = coupon, live
        self.reserved, self.confirmed = [], []

    def get_by_code(self, code):
        return self.coupon if self.coupon and self.coupon.code == code else None

    def count_live_redemptions(self, coupon_id):
        return self.live

    def count_live_redemptions_by_founder(self, coupon_id, founder_id):
        return 0

    def reserve(self, **kw):
        self.reserved.append(kw)

    def confirm_for_payment(self, payment_id, *, at):
        self.confirmed.append(payment_id)


class FakeGateway:
    key_id = "rzp_test_key"

    def __init__(self):
        self.plans_created, self.subs_created, self.cancelled = [], [], []
        self.subscriptions: dict[str, dict] = {}

    def create_plan(self, **kw):
        self.plans_created.append(kw)
        return f"plan_{len(self.plans_created)}"

    def create_subscription(self, **kw):
        sid = f"sub_{len(self.subs_created) + 1}"
        self.subs_created.append(kw)
        self.subscriptions[sid] = {"id": sid, "status": "created", "start_at": kw["start_at"]}
        return {"id": sid, "status": "created"}

    def fetch_subscription(self, sid):
        return self.subscriptions[sid]

    def cancel_subscription(self, sid, *, at_cycle_end):
        self.cancelled.append((sid, at_cycle_end))
        return {"id": sid, "status": "cancelled"}

    def verify_subscription_signature(self, *, subscription_id, payment_id, signature):
        expected = hmac.new(KEY_SECRET.encode(), f"{payment_id}|{subscription_id}".encode(),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")


class _Db:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeSubRepo:
    def __init__(self):
        self.db = _Db()
        self.gateway_plans: dict = {}
        self.payments: dict[int, dict] = {}
        self.subs: dict[int, dict] = {}
        self.plans: dict[int, str] = {}
        self.emails: dict[int, str] = {}
        self.fail_insert_once = False

    # gateway plans
    def get_gateway_plan(self, *, tier, amount_inr, period):
        return self.gateway_plans.get((tier, amount_inr, period))

    def save_gateway_plan(self, *, gateway_plan_id, tier, amount_inr, period):
        return self.gateway_plans.setdefault((tier, amount_inr, period), gateway_plan_id)

    # payments
    def create_trial_payment(self, **kw):
        pid = len(self.payments) + 1
        self.payments[pid] = {**kw, "payment_id": pid, "status": "pending",
                              "gateway_payment_id": None}
        return pid

    def attach_coupon(self, payment_id, *, coupon_id):
        self.payments[payment_id]["coupon_id"] = coupon_id

    def pending_trial_payment(self, gsid):
        for p in self.payments.values():
            if p.get("gateway_subscription_id") == gsid and p["status"] == "pending":
                return {"payment_id": p["payment_id"], "founder_id": p["founder_id"],
                        "amount_inr": p["amount_inr"], "plan_tier": p["plan_tier"]}
        return None

    def payment_recorded(self, gpid):
        return any(p.get("gateway_payment_id") == gpid for p in self.payments.values())

    def mark_payment_success(self, payment_id, *, gateway_payment_id, paid_at, subscription_id):
        self.payments[payment_id].update(status="success", gateway_payment_id=gateway_payment_id,
                                         subscription_id=subscription_id)

    def record_recurring_payment(self, **kw):
        pid = len(self.payments) + 1
        self.payments[pid] = {**kw, "payment_id": pid, "status": "success"}
        return pid

    # subscriptions
    def _obj(self, row):
        return AutopaySubscription(**{k: row.get(k) for k in (
            "subscription_id", "founder_id", "plan_type", "status", "gateway_subscription_id",
            "started_at", "trial_ends_at", "expires_at", "cancelled_at")},
            amount_inr=row["amount_inr"])

    def by_gateway_id(self, gsid):
        for r in self.subs.values():
            if r["gateway_subscription_id"] == gsid:
                return self._obj(r)
        return None

    def live_for_founder(self, founder_id):
        for r in self.subs.values():
            if r["founder_id"] == founder_id and r["status"] in ("trial", "active"):
                return self._obj(r)
        return None

    def create_trial_subscription(self, *, founder_id, plan_type, amount_inr,
                                  gateway_subscription_id, started_at, trial_ends_at):
        if self.fail_insert_once:
            self.fail_insert_once = False
            raise IntegrityError("dup", {}, Exception())
        sid = len(self.subs) + 1
        self.subs[sid] = dict(subscription_id=sid, founder_id=founder_id, plan_type=plan_type,
                              status="trial", gateway_subscription_id=gateway_subscription_id,
                              started_at=started_at, trial_ends_at=trial_ends_at,
                              expires_at=trial_ends_at, cancelled_at=None,
                              amount_inr=amount_inr, reminder_sent_at=None)
        return sid

    def update_subscription(self, sid, **fields):
        self.subs[sid].update(fields)

    def founder_email(self, founder_id):
        return self.emails.get(founder_id, f"f{founder_id}@example.com"), "Asha"

    def set_plan(self, founder_id, plan_type, *, commit=True):
        self.plans[founder_id] = plan_type

    def ended_access(self, *, now, live_grace_until):
        out = []
        for r in self.subs.values():
            exp = r["expires_at"]
            if exp is None:
                continue
            if (r["status"] in ("cancelled", "halted") and exp <= now) or \
               (r["status"] in ("trial", "active") and exp <= live_grace_until):
                out.append(self._obj(r))
        return out

    def other_live_access(self, founder_id, *, excluding, now):
        return False

    def trials_needing_reminder(self, *, now, until):
        return [self._obj(r) for r in self.subs.values()
                if r["status"] == "trial" and r["reminder_sent_at"] is None
                and now < r["trial_ends_at"] <= until]


class FakeCredits:
    def __init__(self):
        self.grants = []

    def adjust(self, founder_id, **kw):
        self.grants.append((founder_id, kw["amount"]))


def build(*, coupon=None, live=0, clock=NOW):
    gateway, repo, credits = FakeGateway(), FakeSubRepo(), FakeCredits()
    crepo = FakeCouponRepo(coupon or trial_coupon(), live=live)
    coupons = CouponService(crepo, clock=lambda: clock)
    svc = SubscriptionService(gateway, repo, credits, coupons, clock=lambda: clock)
    return svc, gateway, repo, credits, crepo


def sign(sub_id, pay_id):
    return hmac.new(KEY_SECRET.encode(), f"{pay_id}|{sub_id}".encode(),
                    hashlib.sha256).hexdigest()


def event(name, sub_id, *, status="authenticated", start_at=None, current_end=None,
          payment=None):
    sub = {"id": sub_id, "status": status}
    if start_at:
        sub["start_at"] = int(start_at.timestamp())
    if current_end:
        sub["current_end"] = int(current_end.timestamp())
    body = {"subscription": {"entity": sub}}
    if payment:
        body["payment"] = {"entity": payment}
    return {"event": name, "payload": body}


def started(svc, founder_id=1):
    return svc.start_trial(founder_id, PlanTier.PRO, "100founders")


# --- starting a trial ----------------------------------------------------------

def test_trial_charges_11_today_and_999_monthly_from_day_8():
    svc, gw, repo, _, crepo = build()
    s = started(svc)

    assert s.upfront_paise == 1100 and s.recurring_paise == 99900
    assert s.trial_days == 7 and s.trial_ends_at == NOW + timedelta(days=7)
    plan = gw.plans_created[0]
    assert plan["amount_paise"] == 99900 and plan["period"] == "monthly"
    sub = gw.subs_created[0]
    assert sub["upfront_paise"] == 1100
    assert sub["start_at"] == int((NOW + timedelta(days=7)).timestamp())
    assert sub["plan_id"] == "plan_1"
    # One pending payment for the fee, the coupon slot claimed against it.
    (pay,) = repo.payments.values()
    assert pay["amount_inr"] == 11 and pay["status"] == "pending"
    assert crepo.reserved[0]["payment_id"] == pay["payment_id"]


def test_the_monthly_plan_is_created_once_and_reused():
    svc, gw, *_ = build()
    started(svc, 1)
    started(svc, 2)
    assert len(gw.plans_created) == 1
    assert [s["plan_id"] for s in gw.subs_created] == ["plan_1", "plan_1"]


def test_a_plain_discount_code_cannot_start_a_trial():
    svc, *_ = build(coupon=trial_coupon(trial_days=None))
    with pytest.raises(CouponNotTrialError):
        started(svc)


def test_the_101st_founder_is_turned_away():
    svc, gw, repo, *_ = build(live=100)
    with pytest.raises(CouponFullyRedeemedError):
        started(svc)
    assert gw.subs_created == [] and repo.payments == {}


def test_one_live_autopay_per_founder():
    svc, *_ = build()
    s = started(svc)
    svc.handle_event("subscription.authenticated",
                     event("subscription.authenticated", s.subscription_id,
                           start_at=s.trial_ends_at))
    with pytest.raises(AutopayAlreadyActiveError):
        started(svc)


def test_a_trial_code_is_refused_by_the_one_time_checkout():
    """Otherwise ₹11 would buy a whole month with no autopay behind it."""
    crepo = FakeCouponRepo(trial_coupon())
    coupons = CouponService(crepo, clock=lambda: NOW)
    with pytest.raises(CouponStartsTrialError):
        coupons.reserve(code="100FOUNDERS", tier=PlanTier.PRO, founder_id=1, payment_id=9)


# --- activation ---------------------------------------------------------------

def test_authenticated_grants_pro_for_the_trial_and_spends_the_slot():
    svc, gw, repo, credits, crepo = build()
    s = started(svc)
    r = svc.handle_event("subscription.authenticated", event(
        "subscription.authenticated", s.subscription_id, start_at=s.trial_ends_at,
        payment={"id": "pay_fee", "amount": 1100}))

    assert r.outcome == WebhookOutcome.CAPTURED
    assert repo.plans[1] == "pro"
    (sub,) = repo.subs.values()
    assert sub["status"] == "trial" and sub["trial_ends_at"] == s.trial_ends_at
    assert sub["expires_at"] == s.trial_ends_at  # access runs to the first charge
    assert repo.payments[1]["status"] == "success"
    assert repo.payments[1]["gateway_payment_id"] == "pay_fee"
    assert crepo.confirmed == [1]
    assert credits.grants == [(1, PRO.monthly_credits)]


def test_activation_is_idempotent():
    svc, gw, repo, credits, _ = build()
    s = started(svc)
    ev = event("subscription.authenticated", s.subscription_id, start_at=s.trial_ends_at)
    svc.handle_event("subscription.authenticated", ev)
    r = svc.handle_event("subscription.authenticated", ev)
    assert r.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert len(repo.subs) == 1 and len(credits.grants) == 1


def test_a_lost_race_between_webhook_and_confirm_is_a_no_op():
    svc, gw, repo, credits, _ = build()
    s = started(svc)
    repo.fail_insert_once = True
    r = svc.handle_event("subscription.authenticated", event(
        "subscription.authenticated", s.subscription_id, start_at=s.trial_ends_at))
    assert r.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert repo.db.rollbacks == 1 and credits.grants == []


def test_confirm_reads_razorpay_before_granting():
    svc, gw, repo, *_ = build()
    s = started(svc)
    sid = s.subscription_id
    # Still "created" at Razorpay: the mandate was not approved.
    r = svc.confirm_trial(1, subscription_id=sid, payment_id="pay_x",
                          signature=sign(sid, "pay_x"))
    assert r.outcome == WebhookOutcome.NOT_CAPTURED and 1 not in repo.plans

    gw.subscriptions[sid].update(status="authenticated")
    r = svc.confirm_trial(1, subscription_id=sid, payment_id="pay_x",
                          signature=sign(sid, "pay_x"))
    assert r.outcome == WebhookOutcome.CAPTURED and repo.plans[1] == "pro"


def test_confirm_rejects_a_forged_signature_and_someone_elses_subscription():
    svc, gw, repo, *_ = build()
    s = started(svc)
    gw.subscriptions[s.subscription_id].update(status="authenticated")
    with pytest.raises(InvalidCheckoutCallbackError):
        svc.confirm_trial(1, subscription_id=s.subscription_id, payment_id="pay_x",
                          signature="forged")
    with pytest.raises(InvalidCheckoutCallbackError):
        svc.confirm_trial(2, subscription_id=s.subscription_id, payment_id="pay_x",
                          signature=sign(s.subscription_id, "pay_x"))


# --- recurring charges ------------------------------------------------------------

def _activated(svc):
    s = started(svc)
    svc.handle_event("subscription.authenticated", event(
        "subscription.authenticated", s.subscription_id, start_at=s.trial_ends_at))
    return s


def test_the_day_8_charge_extends_pro_a_month_and_grants_credits():
    svc, gw, repo, credits, _ = build()
    s = _activated(svc)
    month_end = s.trial_ends_at + timedelta(days=31)
    r = svc.handle_event("subscription.charged", event(
        "subscription.charged", s.subscription_id, status="active", current_end=month_end,
        payment={"id": "pay_999", "amount": 99900}))

    assert r.outcome == WebhookOutcome.CAPTURED
    (sub,) = repo.subs.values()
    assert sub["status"] == "active" and sub["expires_at"] == month_end
    charge = [p for p in repo.payments.values() if p.get("gateway_payment_id") == "pay_999"]
    assert charge[0]["amount_inr"] == 999
    assert len(credits.grants) == 2


def test_a_redelivered_charge_is_recorded_once():
    svc, gw, repo, credits, _ = build()
    s = _activated(svc)
    ev = event("subscription.charged", s.subscription_id, status="active",
               current_end=s.trial_ends_at + timedelta(days=31),
               payment={"id": "pay_999", "amount": 99900})
    svc.handle_event("subscription.charged", ev)
    r = svc.handle_event("subscription.charged", ev)
    assert r.outcome == WebhookOutcome.ALREADY_PROCESSED
    assert len(credits.grants) == 2


def test_the_trial_fee_reported_as_a_charge_is_not_a_renewal():
    svc, gw, repo, credits, _ = build()
    s = _activated(svc)
    r = svc.handle_event("subscription.charged", event(
        "subscription.charged", s.subscription_id, status="authenticated",
        payment={"id": "pay_fee", "amount": 1100}))
    assert r.outcome == WebhookOutcome.ALREADY_PROCESSED
    (sub,) = repo.subs.values()
    assert sub["status"] == "trial" and len(credits.grants) == 1


# --- cancelling and losing access --------------------------------------------------

def test_cancel_during_trial_stops_autopay_now_and_keeps_access_to_day_7():
    svc, gw, repo, *_ = build()
    s = _activated(svc)
    sub = svc.cancel(1)
    assert gw.cancelled == [(s.subscription_id, False)]
    assert sub.status == "cancelled" and sub.expires_at == s.trial_ends_at
    assert repo.plans[1] == "pro"  # still theirs until the trial ends


def test_cancel_after_paying_keeps_the_paid_month():
    svc, gw, repo, *_ = build()
    s = _activated(svc)
    svc.handle_event("subscription.charged", event(
        "subscription.charged", s.subscription_id, status="active",
        current_end=s.trial_ends_at + timedelta(days=31),
        payment={"id": "pay_999", "amount": 99900}))
    svc.cancel(1)
    assert gw.cancelled == [(s.subscription_id, True)]


def test_cancel_with_nothing_to_cancel():
    svc, *_ = build()
    with pytest.raises(NoAutopaySubscriptionError):
        svc.cancel(1)


def test_cancelled_trial_goes_back_to_free_after_day_7_not_before():
    svc, gw, repo, *_ = build()
    s = _activated(svc)
    svc.cancel(1)

    assert svc.expire_ended() == {"expired": 0, "kept_other_access": 0}
    assert repo.plans[1] == "pro"

    later = build(clock=s.trial_ends_at + timedelta(minutes=1))[0]
    later.repository, later.coupons = repo, svc.coupons
    assert later.expire_ended()["expired"] == 1
    assert repo.plans[1] == "free"
    (sub,) = repo.subs.values()
    assert sub["status"] == "expired"


def test_a_slow_renewal_gets_a_grace_window_then_access_ends():
    svc, gw, repo, *_ = build()
    s = _activated(svc)

    within = build(clock=s.trial_ends_at + RENEWAL_GRACE - timedelta(hours=1))[0]
    within.repository = repo
    assert within.expire_ended()["expired"] == 0 and repo.plans[1] == "pro"

    past = build(clock=s.trial_ends_at + RENEWAL_GRACE + timedelta(hours=1))[0]
    past.repository = repo
    assert past.expire_ended()["expired"] == 1 and repo.plans[1] == "free"


def test_halted_after_failed_charges_ends_access_at_the_paid_date():
    svc, gw, repo, *_ = build()
    s = _activated(svc)
    svc.handle_event("subscription.halted",
                     event("subscription.halted", s.subscription_id, status="halted"))
    (sub,) = repo.subs.values()
    assert sub["status"] == "halted"
    after = build(clock=s.trial_ends_at + timedelta(seconds=1))[0]
    after.repository = repo
    assert after.expire_ended()["expired"] == 1 and repo.plans[1] == "free"


def test_team_accounts_are_never_moved_to_free():
    from app.core.config import settings

    svc, gw, repo, *_ = build()
    repo.emails[1] = sorted(settings.team_full_access_emails)[0]
    s = _activated(svc)
    svc.cancel(1)
    after = build(clock=s.trial_ends_at + timedelta(days=1))[0]
    after.repository = repo
    assert after.expire_ended() == {"expired": 0, "kept_other_access": 1}
    assert repo.plans[1] == "pro"


# --- reminder ------------------------------------------------------------------------

def test_one_reminder_two_days_before_the_first_charge():
    svc, gw, repo, *_ = build()
    s = _activated(svc)
    sent = []

    early = build(clock=s.trial_ends_at - timedelta(days=3))[0]
    early.repository = repo
    assert early.send_trial_reminders(lambda *a: sent.append(a) or True) == {"reminders_sent": 0}

    due = build(clock=s.trial_ends_at - timedelta(days=1))[0]
    due.repository = repo
    assert due.send_trial_reminders(lambda *a: sent.append(a) or True) == {"reminders_sent": 1}
    assert due.send_trial_reminders(lambda *a: sent.append(a) or True) == {"reminders_sent": 0}

    to, subject, body = sent[0]
    assert to == "f1@example.com"
    assert "₹999" in body and "Cancel" in body


def test_unknown_lifecycle_events_change_nothing():
    svc, gw, repo, *_ = build()
    r = svc.handle_event("subscription.cancelled",
                         event("subscription.cancelled", "sub_unknown", status="cancelled"))
    assert r.outcome == WebhookOutcome.UNKNOWN_PAYMENT and repo.plans == {}


# --- the real Razorpay client, over a mock transport -----------------------------------

def _gateway(handler):
    import httpx

    from app.payments.gateway import RAZORPAY_API_BASE, RazorpayGateway
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=RAZORPAY_API_BASE,
                          auth=("rzp_test_key", KEY_SECRET))
    return RazorpayGateway(key_id="rzp_test_key", key_secret=KEY_SECRET,
                           webhook_secret="whsec", client=client)


def test_gateway_sends_the_trial_shape_razorpay_expects():
    import json as _json

    import httpx
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, _json.loads(request.content or b"{}")))
        if request.url.path.endswith("/plans"):
            return httpx.Response(200, json={"id": "plan_A"})
        return httpx.Response(200, json={"id": "sub_A", "status": "created"})

    gw = _gateway(handler)
    assert gw.create_plan(amount_paise=99900, period="monthly", interval=1,
                          name="Ally Pro (monthly)", notes={}) == "plan_A"
    gw.create_subscription(plan_id="plan_A", start_at=1_800_000_000, total_count=120,
                           upfront_paise=1100, upfront_name="7-day Pro trial", notes={"a": "b"})
    gw.cancel_subscription("sub_A", at_cycle_end=False)

    plan = seen[0][2]
    assert seen[0][:2] == ("POST", "/v1/plans")
    assert plan["item"]["amount"] == 99900 and plan["period"] == "monthly"
    sub = seen[1][2]
    assert sub["plan_id"] == "plan_A" and sub["start_at"] == 1_800_000_000
    assert sub["addons"] == [{"item": {"name": "7-day Pro trial", "amount": 1100,
                                       "currency": "INR"}}]
    assert sub["customer_notify"] == 1 and sub["total_count"] == 120
    assert seen[2][:2] == ("POST", "/v1/subscriptions/sub_A/cancel")
    assert seen[2][2] == {"cancel_at_cycle_end": 0}


def test_gateway_errors_carry_razorpays_reason():
    import httpx

    from app.payments.gateway import PaymentGatewayError

    gw = _gateway(lambda r: httpx.Response(
        400, json={"error": {"code": "BAD_REQUEST_ERROR",
                             "description": "subscriptions not enabled"}}))
    with pytest.raises(PaymentGatewayError) as err:
        gw.fetch_subscription("sub_A")
    assert "subscriptions not enabled" in str(err.value)


def test_subscription_checkout_signature_is_payment_then_subscription():
    gw = _gateway(lambda r: None)
    good = sign("sub_A", "pay_A")
    assert gw.verify_subscription_signature(subscription_id="sub_A", payment_id="pay_A",
                                            signature=good)
    # The order-based shape (subscription first) must not verify.
    wrong = hmac.new(KEY_SECRET.encode(), b"sub_A|pay_A", hashlib.sha256).hexdigest()
    assert not gw.verify_subscription_signature(subscription_id="sub_A", payment_id="pay_A",
                                                signature=wrong)


# --- webhook routing in PaymentService --------------------------------------------------

def test_webhook_routes_subscription_events_and_keeps_their_payments_out_of_orders():
    import json as _json

    from app.payments.models import WebhookResult
    from app.payments.service import PaymentService

    class Gw:
        def verify_webhook_signature(self, *, body, signature):
            return True

    class Subs:
        def __init__(self):
            self.events = []

        def handle_event(self, name, payload):
            self.events.append(name)
            return WebhookResult(outcome=WebhookOutcome.CAPTURED)

    class Repo:
        def get_by_gateway_payment_id(self, _):
            raise AssertionError("subscription payment reached the order path")

        get_by_gateway_order_id = get_by_gateway_payment_id

    subs = Subs()
    svc = PaymentService(Gw(), Repo(), credits=None, subscriptions=subs)
    body = _json.dumps({"event": "subscription.charged", "payload": {}}).encode()
    assert svc.handle_webhook(body=body, signature="x").outcome == WebhookOutcome.CAPTURED
    assert subs.events == ["subscription.charged"]

    for ev in ("payment.captured", "payment.failed"):
        body = _json.dumps({"event": ev, "payload": {"payment": {"entity": {
            "id": "pay_1", "order_id": "order_rzp", "subscription_id": "sub_A"}}}}).encode()
        assert svc.handle_webhook(body=body, signature="x").outcome == \
            WebhookOutcome.IGNORED_EVENT
