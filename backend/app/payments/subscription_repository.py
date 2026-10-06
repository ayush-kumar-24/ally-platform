"""SQL for autopay subscriptions (Razorpay Subscriptions + a paid trial).

Kept apart from repository.py, which serves the one-time order checkout and
whose `create_subscription` hard-codes an `active`, gateway-less row. Raw
`text()` SQL like its sibling, for the same reason: several of these columns
(payments.plan_tier, coupon_id, gateway_subscription_id) are not on the ORM
classes.

Every write commits unless told not to, matching PaymentRepository: the
service decides where the transaction boundaries that matter are.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Statuses during which the founder holds the plan and autopay is running.
LIVE_STATUSES = ("trial", "active")


@dataclass(frozen=True)
class AutopaySubscription:
    subscription_id: int
    founder_id: int
    plan_type: str
    status: str
    gateway_subscription_id: str
    started_at: datetime | None
    trial_ends_at: datetime | None
    expires_at: datetime | None
    cancelled_at: datetime | None
    amount_inr: int


def _to_sub(row) -> AutopaySubscription | None:
    if row is None:
        return None
    return AutopaySubscription(
        subscription_id=row["subscription_id"], founder_id=row["founder_id"],
        plan_type=row["plan_type"], status=row["status"],
        gateway_subscription_id=row["gateway_subscription_id"],
        started_at=row["started_at"], trial_ends_at=row["trial_ends_at"],
        expires_at=row["expires_at"], cancelled_at=row["cancelled_at"],
        amount_inr=int(row["amount_inr"] or 0),
    )


_SUB_COLUMNS = ("subscription_id, founder_id, plan_type, status, gateway_subscription_id, "
                "started_at, trial_ends_at, expires_at, cancelled_at, amount_inr")


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- gateway plans ------------------------------------------------------

    def get_gateway_plan(self, *, tier: str, amount_inr: int, period: str) -> str | None:
        return self.db.execute(
            text("SELECT gateway_plan_id FROM gateway_plans WHERE gateway = 'razorpay' "
                 "AND plan_tier = :tier AND amount_inr = :amt AND period = :period"),
            {"tier": tier, "amt": amount_inr, "period": period},
        ).scalar()

    def save_gateway_plan(self, *, gateway_plan_id: str, tier: str, amount_inr: int,
                          period: str) -> str:
        """Record a newly created gateway plan. Two first-ever trials racing
        can each create one at Razorpay; the unique key keeps the first and
        the loser reads it back, so every later subscription shares one plan."""
        self.db.execute(
            text("INSERT INTO gateway_plans (gateway_plan_id, gateway, plan_tier, "
                 "amount_inr, period) VALUES (:pid, 'razorpay', :tier, :amt, :period) "
                 "ON CONFLICT ON CONSTRAINT gateway_plans_identity_key DO NOTHING"),
            {"pid": gateway_plan_id, "tier": tier, "amt": amount_inr, "period": period},
        )
        self.db.commit()
        return self.get_gateway_plan(tier=tier, amount_inr=amount_inr, period=period) \
            or gateway_plan_id

    # --- payments -------------------------------------------------------------

    def create_trial_payment(self, *, founder_id: int, amount_inr: int, plan_tier: str,
                             gateway_subscription_id: str, list_amount_inr: int | None,
                             discount_inr: int | None) -> int:
        """The upfront trial fee, pending until Razorpay reports it paid.
        Not committed: the coupon reservation joins this transaction."""
        return self.db.execute(
            text("""INSERT INTO payments (founder_id, amount_inr, currency, status,
                        payment_gateway, gateway_subscription_id, plan_tier,
                        list_amount_inr, discount_inr)
                    VALUES (:fid, :amt, 'INR', 'pending', 'razorpay', :gsid, :tier,
                            :list, :disc)
                    RETURNING payment_id"""),
            {"fid": founder_id, "amt": amount_inr, "gsid": gateway_subscription_id,
             "tier": plan_tier, "list": list_amount_inr, "disc": discount_inr},
        ).scalar()

    def attach_coupon(self, payment_id: int, *, coupon_id: int) -> None:
        self.db.execute(text("UPDATE payments SET coupon_id = :cid WHERE payment_id = :pid"),
                        {"cid": coupon_id, "pid": payment_id})
        self.db.commit()

    def pending_trial_payment(self, gateway_subscription_id: str) -> dict | None:
        row = self.db.execute(
            text("""SELECT payment_id, founder_id, amount_inr, plan_tier FROM payments
                    WHERE gateway_subscription_id = :gsid AND status = 'pending'
                    ORDER BY payment_id LIMIT 1"""),
            {"gsid": gateway_subscription_id},
        ).mappings().first()
        return dict(row) if row else None

    def payment_recorded(self, gateway_payment_id: str) -> bool:
        return self.db.execute(
            text("SELECT 1 FROM payments WHERE gateway_payment_id = :gpid LIMIT 1"),
            {"gpid": gateway_payment_id},
        ).first() is not None

    def mark_payment_success(self, payment_id: int, *, gateway_payment_id: str | None,
                             paid_at: datetime, subscription_id: int) -> None:
        self.db.execute(
            text("""UPDATE payments SET status = 'success', gateway_payment_id = :gpid,
                        paid_at = :at, subscription_id = :sid
                    WHERE payment_id = :pid"""),
            {"gpid": gateway_payment_id, "at": paid_at, "sid": subscription_id,
             "pid": payment_id},
        )
        self.db.commit()

    def mark_payment_failed(self, payment_id: int, *, reason: str) -> None:
        self.db.execute(
            text("UPDATE payments SET status = 'failed', failure_reason = :r "
                 "WHERE payment_id = :pid AND status = 'pending'"),
            {"r": reason, "pid": payment_id},
        )
        self.db.commit()

    def record_recurring_payment(self, *, founder_id: int, amount_inr: int, plan_tier: str,
                                 gateway_payment_id: str, gateway_subscription_id: str,
                                 subscription_id: int, paid_at: datetime) -> int:
        payment_id = self.db.execute(
            text("""INSERT INTO payments (founder_id, amount_inr, currency, status,
                        payment_gateway, gateway_payment_id, gateway_subscription_id,
                        plan_tier, subscription_id, paid_at)
                    VALUES (:fid, :amt, 'INR', 'success', 'razorpay', :gpid, :gsid,
                            :tier, :sid, :at)
                    RETURNING payment_id"""),
            {"fid": founder_id, "amt": amount_inr, "gpid": gateway_payment_id,
             "gsid": gateway_subscription_id, "tier": plan_tier, "sid": subscription_id,
             "at": paid_at},
        ).scalar()
        self.db.commit()
        return payment_id

    # --- subscriptions --------------------------------------------------------

    def by_gateway_id(self, gateway_subscription_id: str) -> AutopaySubscription | None:
        row = self.db.execute(
            text(f"SELECT {_SUB_COLUMNS} FROM subscriptions "
                 "WHERE gateway_subscription_id = :gsid"),
            {"gsid": gateway_subscription_id},
        ).mappings().first()
        return _to_sub(row)

    def live_for_founder(self, founder_id: int) -> AutopaySubscription | None:
        row = self.db.execute(
            text(f"""SELECT {_SUB_COLUMNS} FROM subscriptions
                     WHERE founder_id = :fid AND gateway_subscription_id IS NOT NULL
                       AND status IN ('trial', 'active')
                     ORDER BY started_at DESC, subscription_id DESC LIMIT 1"""),
            {"fid": founder_id},
        ).mappings().first()
        return _to_sub(row)

    def create_trial_subscription(self, *, founder_id: int, plan_type: str, amount_inr: int,
                                  gateway_subscription_id: str, started_at: datetime,
                                  trial_ends_at: datetime) -> int:
        """Not committed on its own: the caller marks the payment and grants
        the plan in the same breath. Raises IntegrityError if another delivery
        of the same event got here first (unique gateway_subscription_id)."""
        return self.db.execute(
            text("""INSERT INTO subscriptions (founder_id, plan_type, status, started_at,
                        billing_cycle, amount_inr, expires_at, trial_ends_at,
                        payment_gateway, gateway_subscription_id)
                    VALUES (:fid, :plan, 'trial', :start, 'monthly', :amt, :trial_end,
                            :trial_end, 'razorpay', :gsid)
                    RETURNING subscription_id"""),
            {"fid": founder_id, "plan": plan_type, "start": started_at, "amt": amount_inr,
             "trial_end": trial_ends_at, "gsid": gateway_subscription_id},
        ).scalar()

    def update_subscription(self, subscription_id: int, **fields) -> None:
        allowed = {"status", "expires_at", "cancelled_at", "cancellation_reason",
                   "reminder_sent_at"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        assignments = ", ".join(f"{k} = :{k}" for k in sets)
        self.db.execute(
            text(f"UPDATE subscriptions SET {assignments}, updated_at = now() "
                 "WHERE subscription_id = :sid"),
            {**sets, "sid": subscription_id},
        )
        self.db.commit()

    # --- founder plan -----------------------------------------------------------

    def founder_email(self, founder_id: int) -> tuple[str | None, str | None]:
        row = self.db.execute(
            text("SELECT email, full_name FROM founders WHERE founder_id = :fid"),
            {"fid": founder_id},
        ).first()
        return (row[0], row[1]) if row else (None, None)

    def set_plan(self, founder_id: int, plan_type: str, *, commit: bool = True) -> None:
        self.db.execute(
            text("UPDATE founders SET plan_type = :plan, updated_at = now() "
                 "WHERE founder_id = :fid"),
            {"plan": plan_type, "fid": founder_id},
        )
        if commit:
            self.db.commit()

    # --- sweeps -------------------------------------------------------------------

    def ended_access(self, *, now: datetime, live_grace_until: datetime) -> list[AutopaySubscription]:
        """Autopay subscriptions whose paid-for access is over.

        Ended ones (cancelled / halted / completed) lose access once
        `expires_at` passes. Live ones (trial / active) get a grace window
        first: a UPI AutoPay debit is announced 24h ahead and can land a day
        late, so a renewal that is merely slow must not cost anyone access.
        Only rows that still have a live status or have not been closed out
        are returned -- each is handled once.
        """
        rows = self.db.execute(
            text(f"""SELECT {_SUB_COLUMNS} FROM subscriptions
                     WHERE gateway_subscription_id IS NOT NULL
                       AND expires_at IS NOT NULL
                       AND (
                         (status IN ('cancelled', 'halted') AND expires_at <= :now)
                         OR (status IN ('trial', 'active') AND expires_at <= :grace)
                       )"""),
            {"now": now, "grace": live_grace_until},
        ).mappings().all()
        return [_to_sub(r) for r in rows]

    def other_live_access(self, founder_id: int, *, excluding: int, now: datetime) -> bool:
        """Does the founder hold the plan through anything else -- another
        autopay subscription, or a one-time purchase still inside its month?"""
        return self.db.execute(
            text("""SELECT 1 FROM subscriptions
                    WHERE founder_id = :fid AND subscription_id <> :sid
                      AND status IN ('trial', 'active')
                      AND (expires_at IS NULL OR expires_at > :now)
                    LIMIT 1"""),
            {"fid": founder_id, "sid": excluding, "now": now},
        ).first() is not None

    def trials_needing_reminder(self, *, now: datetime, until: datetime) -> list[AutopaySubscription]:
        rows = self.db.execute(
            text(f"""SELECT {_SUB_COLUMNS} FROM subscriptions
                     WHERE gateway_subscription_id IS NOT NULL
                       AND status = 'trial' AND reminder_sent_at IS NULL
                       AND trial_ends_at > :now AND trial_ends_at <= :until"""),
            {"now": now, "until": until},
        ).mappings().all()
        return [_to_sub(r) for r in rows]
