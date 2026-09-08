"""The expiry sweep -- what makes paid access actually end.

Without this job every date billing writes is decoration: a cancelled founder
keeps their features, a halted subscription keeps its features, and a month
bought once lasts forever. That was the state of things, and these tests are
what stop it returning.

Two properties matter more than the rest and are each worth reading twice:

  1. It must not downgrade a founder who actually paid. A charge whose webhook
     was lost looks identical to a lapse from inside this database, so the
     sweep asks Razorpay before acting.
  2. It must not touch a plan a subscription did not grant. An admin who comps
     someone to Pro creates no subscription row, and a nightly job does not get
     to quietly revoke that.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.payments.expiry import SubscriptionExpirySweep
from app.plans.catalog import DEFAULT_TIER

from tests.test_payments_subscriptions import (   # the same doubles, one definition
    FakePaymentRepository,
    FakeSubscriptionRepository,
)

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


class _Reconciler:
    """Stands in for SubscriptionService.reconcile. `recovers` is the set of
    subscription ids Razorpay would report as still paid."""

    def __init__(self, recovers=(), raises=False):
        self.recovers = set(recovers)
        self.raises = raises
        self.asked = []

    def reconcile(self, subscription):
        self.asked.append(subscription.subscription_id)
        if self.raises:
            raise RuntimeError("gateway exploded")
        return subscription.subscription_id in self.recovers


def _lapsed_subscription(repo, *, founder_id=42, tier="starter", status="cancelled",
                         access_until=None):
    sid = repo.create_pending(founder_id=founder_id, plan_type=tier, amount_inr=499,
                              gateway_subscription_id=f"sub_{sid_counter()}",
                              razorpay_plan_id="plan_PLUS", status=status)
    repo.sync_from_entity(sid, status=status)
    repo.set_access_until(sid, access_until or NOW - timedelta(days=1))
    return sid


_counter = {"n": 0}


def sid_counter():
    _counter["n"] += 1
    return _counter["n"]


def _sweep(repo=None, payments=None, reconciler=None, now=NOW):
    repo = repo or FakeSubscriptionRepository()
    # ONE session, as the container wires it -- which is what makes "mark
    # expired and downgrade in one transaction" a real claim rather than a
    # comment.
    payments = payments or FakePaymentRepository(db=repo.db)
    return (SubscriptionExpirySweep(repo, payments, subscriptions=reconciler,
                                    clock=lambda: now),
            repo, payments)


def test_nothing_to_do_is_a_clean_run():
    sweep, *_ = _sweep()
    assert sweep.run().as_dict()["expired"] == 0


def test_a_lapsed_subscription_downgrades_the_founder_to_free():
    repo = FakeSubscriptionRepository()
    sweep, repo, payments = _sweep(repo=repo)
    sid = _lapsed_subscription(repo)

    result = sweep.run().as_dict()

    assert result["expired"] == 1
    assert result["founders_downgraded"] == [42]
    assert payments.plans_granted == [(42, DEFAULT_TIER.value)]
    assert repo.get_by_id(sid).status == "expired"


def test_a_subscription_still_inside_its_paid_period_is_untouched():
    """The cancelled founder running out the month they paid for. Taking their
    features now is keeping money for a service withdrawn."""
    repo = FakeSubscriptionRepository()
    sweep, repo, payments = _sweep(repo=repo)
    _lapsed_subscription(repo, access_until=NOW + timedelta(days=10))

    assert sweep.run().as_dict()["expired"] == 0
    assert payments.plans_granted == []


def test_the_sweep_is_idempotent():
    """It runs on a schedule; a second pass must find nothing left to do."""
    repo = FakeSubscriptionRepository()
    sweep, repo, payments = _sweep(repo=repo)
    _lapsed_subscription(repo)

    sweep.run()
    second = sweep.run().as_dict()

    assert second["expired"] == 0
    assert len(payments.plans_granted) == 1


def test_a_founder_razorpay_says_has_paid_is_not_downgraded():
    """THE GUARD THAT MATTERS. A lost webhook is indistinguishable from a lapse
    from in here, and downgrading someone who paid is the worst outcome
    available -- worse than a few hours of unpaid access."""
    repo = FakeSubscriptionRepository()
    reconciler = _Reconciler()
    sweep, repo, payments = _sweep(repo=repo, reconciler=reconciler)
    sid = _lapsed_subscription(repo)
    reconciler.recovers.add(sid)

    # reconcile() moving the clock is what "recovered" means to the sweep.
    original = reconciler.reconcile

    def reconcile_and_extend(subscription):
        recovered = original(subscription)
        if recovered:
            repo.set_access_until(subscription.subscription_id, NOW + timedelta(days=30))
        return recovered

    reconciler.reconcile = reconcile_and_extend

    result = sweep.run().as_dict()

    assert result["reconciled"] == 1
    assert result["expired"] == 0
    assert payments.plans_granted == []
    assert repo.get_by_id(sid).status != "expired"


def test_a_reconcile_that_changes_nothing_still_expires():
    """Razorpay agrees the subscription is finished. Nothing recovered it, so
    the founder really has lapsed."""
    repo = FakeSubscriptionRepository()
    sweep, repo, payments = _sweep(repo=repo, reconciler=_Reconciler())
    _lapsed_subscription(repo)

    assert sweep.run().as_dict()["expired"] == 1
    assert payments.plans_granted == [(42, DEFAULT_TIER.value)]


def test_one_bad_row_does_not_stop_the_sweep():
    """Same shape as the deletion sweep: a single failure is logged and the
    rest still run. A job that stops halfway leaves everyone after it entitled
    and reports success."""
    repo = FakeSubscriptionRepository()
    payments = FakePaymentRepository()
    sweep, repo, payments = _sweep(repo=repo, payments=payments)
    first = _lapsed_subscription(repo, founder_id=1)
    _lapsed_subscription(repo, founder_id=2)

    original_grant = payments.grant_plan

    def explode_on_first(founder_id, plan_type):
        if founder_id == 1:
            raise RuntimeError("db gone")
        original_grant(founder_id, plan_type)

    payments.grant_plan = explode_on_first

    result = sweep.run().as_dict()

    assert result["failed"] == 1
    assert result["expired"] == 1
    assert result["founders_downgraded"] == [2]
    assert repo.get_by_id(first).status != "expired"


def test_the_sweep_works_with_no_gateway_at_all():
    """No reconciler configured (payments unwired in this environment). It
    still expires what has plainly run out -- it just cannot double-check
    first."""
    repo = FakeSubscriptionRepository()
    sweep, repo, payments = _sweep(repo=repo, reconciler=None)
    _lapsed_subscription(repo)

    assert sweep.run().as_dict()["expired"] == 1
