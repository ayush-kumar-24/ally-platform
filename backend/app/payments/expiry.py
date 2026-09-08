"""The sweep that makes paid access actually end.

WHAT WAS MISSING. Nothing enforced an expiry. A subscription row carried
`expires_at` and later `access_until`, and no code anywhere read them: a
cancelled founder kept their features, a halted subscription kept its
features, and a Plus month bought once lasted forever. Every other piece of
billing -- the cancel button, the grace window, the period dates -- is
decoration without this.

WHAT IT WILL NOT DO. It never touches a founder whose paid plan did not come
from a subscription row. An admin who sets someone to Pro by hand
(`PATCH /admin/users/{id}/subscription`) creates no subscription, so that
founder cannot appear here at all -- the query requires a row whose
`plan_type` matches theirs. A comped account is not something a nightly job
gets to quietly revoke.

WHAT IT DOES SECOND. Before expiring anything it RECONCILES: it asks Razorpay
about each subscription that looks lapsed but is still live there. A charge
whose webhook was lost looks identical to a lapse from inside this database,
and downgrading a founder who actually paid is the worst outcome available
here -- worse than a few hours of unpaid access. So the gateway gets the last
word, and only a subscription Razorpay also considers finished is expired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.logger import logger
from app.payments.subscription_repository import SubscriptionRepository
from app.plans.catalog import DEFAULT_TIER


@dataclass
class SweepResult:
    checked: int = 0
    expired: int = 0
    reconciled: int = 0
    failed: int = 0
    founders: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"checked": self.checked, "expired": self.expired,
                "reconciled": self.reconciled, "failed": self.failed,
                "founders_downgraded": self.founders}


class SubscriptionExpirySweep:
    def __init__(self, repository: SubscriptionRepository, payments, *,
                 subscriptions=None, clock=None):
        self.repository = repository
        #: PaymentRepository -- `grant_plan` is how a founder's tier is
        #: written everywhere else, including by the admin panel, so a
        #: downgrade goes through the same door rather than its own UPDATE.
        self.payments = payments
        #: SubscriptionService, for the reconcile step. Optional: without a
        #: configured gateway the sweep still expires rows whose access has
        #: run out, it just cannot double-check them first.
        self.subscriptions = subscriptions
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def run(self, *, limit: int = 200) -> SweepResult:
        now = self._now()
        result = SweepResult()

        for subscription in self.repository.find_lapsed(now=now, limit=limit):
            result.checked += 1
            try:
                if self._recovered(subscription, now):
                    result.reconciled += 1
                    continue
                self._expire(subscription, now)
                result.expired += 1
                result.founders.append(subscription.founder_id)
            except Exception as exc:  # noqa: BLE001 -- one founder must not stop the sweep
                # Same shape as the deletion sweep: a single bad row is a
                # logged failure, not a job that silently stops halfway and
                # leaves everyone after it still entitled.
                logger.error("payments: expiry sweep failed for one subscription, continuing",
                             extra={"subscription_id": subscription.subscription_id,
                                    "founder_id": subscription.founder_id,
                                    "error": str(exc)})
                self.repository.db.rollback()
                result.failed += 1

        if result.expired or result.failed:
            logger.info("payments: subscription expiry sweep finished", extra=result.as_dict())
        return result

    def _recovered(self, subscription, now: datetime) -> bool:
        """True when Razorpay says this subscription is fine after all.

        The one guard against downgrading a founder who paid. `reconcile`
        re-reads the subscription entity server-to-server; if Razorpay has
        charged a cycle we never recorded, it re-grants and moves the access
        clock, and this row is no longer lapsed.
        """
        if self.subscriptions is None:
            return False
        if not self.subscriptions.reconcile(subscription):
            return False
        refreshed = self.repository.get_by_id(subscription.subscription_id)
        return bool(refreshed and refreshed.access_until and refreshed.access_until > now)

    def _expire(self, subscription, now: datetime) -> None:
        """Mark the subscription expired and put the founder back on Free.

        Both in one transaction: a founder left on a paid tier with an expired
        subscription row is invisible to the next sweep (the row is no longer
        'not expired'), so a partial application here would strand them on a
        plan nobody is paying for.
        """
        self.repository.mark_expired(subscription.subscription_id, at=now)
        self.payments.grant_plan(subscription.founder_id, DEFAULT_TIER.value)
        logger.info("payments: paid access expired, founder returned to the free plan",
                    extra={"founder_id": subscription.founder_id,
                           "subscription_id": subscription.subscription_id,
                           "was_plan": subscription.plan_type,
                           "status": subscription.status,
                           "access_until": subscription.access_until.isoformat()
                           if subscription.access_until else None})
