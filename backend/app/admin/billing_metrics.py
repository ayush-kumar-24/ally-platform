"""The admin billing dashboard: MRR, subscribers, churn, failed payments.

Every number here is read from `subscriptions`, `payments` and `invoices` --
never from Razorpay's dashboard and never from the plan catalog's list prices
multiplied by a headcount. That distinction is the whole point: MRR computed
from "how many people are on Pro x Rs 999" counts a founder whose card failed
last week, and a coupon-discounted subscription at its undiscounted price.
`subscriptions.amount_inr` is what the founder is actually billed, so that is
what is summed.

WHAT COUNTS AS ACTIVE. A subscription is revenue if its mandate is live at
Razorpay AND its paid access has not run out -- `status IN (...) AND
(access_until IS NULL OR access_until >= now())`. A halted subscription is
excluded the moment its grace ends, which is also the moment the founder
loses access, so the dashboard and the product agree about who is a customer.

WHAT IS DELIBERATELY NOT HERE. Anything Razorpay is the system of record for
and we only mirror: settlement amounts, fees, and tax collected. Reporting a
mirrored copy of those next to figures computed here invites someone to
reconcile them against a Razorpay statement, and the first small drift would
be indistinguishable from a real accounting problem. Refund and invoice counts
ARE here because those rows are ours.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.payments.subscription_repository import LIVE_STATUSES

#: The subscription statuses that represent a paying customer right now.
_ACTIVE_SQL = ", ".join(f"'{s}'" for s in ("active", "pending", "halted"))
_LIVE_SQL = ", ".join(f"'{s}'" for s in LIVE_STATUSES)


@dataclass
class BillingSummary:
    mrr_inr: float = 0.0
    active_subscribers: int = 0
    #: Keyed by tier value ('starter', 'pro', ...). A dict rather than named
    #: fields so adding a tier to the catalog does not need a schema change
    #: here -- the admin panel renders whatever comes back.
    subscribers_by_tier: dict = field(default_factory=dict)
    new_subscriptions: int = 0
    cancelled_subscriptions: int = 0
    #: Subscriptions cancelled but still inside the period they paid for.
    #: Revenue that is already gone but has not shown up in the active count
    #: yet -- the number that makes next month's MRR predictable.
    pending_cancellations: int = 0
    successful_payments: int = 0
    failed_payments: int = 0
    refunds: int = 0
    refunded_amount_inr: float = 0.0
    revenue_inr: float = 0.0
    one_time_purchases: int = 0
    invoice_count: int = 0
    #: Subscriptions Razorpay is retrying, or has given up on, whose founder
    #: still has access. The actionable list on this page: each one is money
    #: expected and not arrived.
    at_risk_subscriptions: int = 0
    outstanding_inr: float = 0.0
    window_days: int = 30

    def as_dict(self) -> dict:
        return asdict(self)


class BillingMetricsService:
    def __init__(self, db: Session, *, clock=None):
        self.db = db
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def summary(self, *, days: int = 30) -> BillingSummary:
        now = self._now()
        since = now - timedelta(days=days)
        s = BillingSummary(window_days=days)

        # --- recurring revenue ---------------------------------------------
        rows = self.db.execute(
            text(f"SELECT plan_type, COUNT(*) AS subscribers, "
                 "       COALESCE(SUM(amount_inr), 0) AS mrr "
                 "FROM subscriptions "
                 f"WHERE status IN ({_ACTIVE_SQL}) AND billing_cycle = 'monthly' "
                 "  AND (access_until IS NULL OR access_until >= :now) "
                 "GROUP BY plan_type"),
            {"now": now},
        ).mappings().all()
        for row in rows:
            s.subscribers_by_tier[row["plan_type"]] = int(row["subscribers"])
            s.active_subscribers += int(row["subscribers"])
            s.mrr_inr += float(row["mrr"])

        # --- movement in the window ----------------------------------------
        s.new_subscriptions = self._scalar(
            "SELECT COUNT(*) FROM subscriptions "
            "WHERE billing_cycle = 'monthly' AND activated_at >= :since", since=since)
        s.cancelled_subscriptions = self._scalar(
            "SELECT COUNT(*) FROM subscriptions WHERE cancelled_at >= :since", since=since)
        s.pending_cancellations = self._scalar(
            "SELECT COUNT(*) FROM subscriptions "
            "WHERE cancel_at_period_end AND status <> 'expired' "
            "  AND access_until IS NOT NULL AND access_until >= :now", now=now)

        # --- payments -------------------------------------------------------
        payments = self.db.execute(
            text("SELECT status, COUNT(*) AS n, COALESCE(SUM(amount_inr), 0) AS total "
                 "FROM payments WHERE created_at >= :since GROUP BY status"),
            {"since": since},
        ).mappings().all()
        for row in payments:
            if row["status"] == "success":
                s.successful_payments = int(row["n"])
                s.revenue_inr = float(row["total"])
            elif row["status"] == "failed":
                s.failed_payments = int(row["n"])
            elif row["status"] == "refunded":
                s.refunds = int(row["n"])
                s.refunded_amount_inr = float(row["total"])

        s.one_time_purchases = self._scalar(
            "SELECT COUNT(*) FROM subscriptions "
            "WHERE billing_cycle = 'one_time' AND started_at >= :since", since=since)
        s.invoice_count = self._scalar(
            "SELECT COUNT(*) FROM invoices WHERE COALESCE(issued_at, created_at) >= :since",
            since=since)

        # --- money expected and not arrived ---------------------------------
        at_risk = self.db.execute(
            text("SELECT COUNT(*) AS n, COALESCE(SUM(amount_inr), 0) AS total "
                 "FROM subscriptions "
                 "WHERE status IN ('pending', 'halted') "
                 "  AND (access_until IS NULL OR access_until >= :now)"),
            {"now": now},
        ).mappings().first()
        if at_risk:
            s.at_risk_subscriptions = int(at_risk["n"])
            s.outstanding_inr = float(at_risk["total"])
        return s

    def at_risk(self, *, limit: int = 50) -> list[dict]:
        """The founders whose renewal did not go through, newest first.

        A list and not just a count because this is the one part of the
        dashboard someone can act on: each row is a founder who is still using
        the product and whose payment has failed, and reaching out before the
        grace window closes is what stops it becoming a cancellation.
        """
        rows = self.db.execute(
            text("SELECT s.subscription_id, s.founder_id, f.email, f.full_name, "
                 "       s.plan_type, s.status, s.amount_inr, s.next_charge_at, "
                 "       s.access_until, s.paid_count "
                 "FROM subscriptions s JOIN founders f ON f.founder_id = s.founder_id "
                 "WHERE s.status IN ('pending', 'halted') "
                 "ORDER BY s.access_until NULLS LAST, s.subscription_id DESC "
                 "LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def recent_subscriptions(self, *, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            text(f"SELECT s.subscription_id, s.founder_id, f.email, s.plan_type, s.status, "
                 "       s.amount_inr, s.paid_count, s.started_at, s.activated_at, "
                 "       s.cancelled_at, s.cancel_at_period_end, s.access_until, "
                 "       s.next_charge_at, s.gateway_subscription_id "
                 "FROM subscriptions s JOIN founders f ON f.founder_id = s.founder_id "
                 f"WHERE s.billing_cycle = 'monthly' AND s.status IN ({_LIVE_SQL}) "
                 "ORDER BY s.subscription_id DESC LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def _scalar(self, sql: str, **params) -> int:
        return int(self.db.execute(text(sql), params).scalar() or 0)
