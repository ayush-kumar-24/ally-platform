"""Raw-SQL reads/writes against payments/subscriptions/founders -- same style
as app/admin/users_db_repository.py: parameterised text() queries, no ORM
model for these tables (schema.py's reflected Payments/Subscriptions classes
exist but this module writes the same defensive, explicit-column way the
rest of the Admin Panel already does)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.payments.models import PaymentRecord


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- payments ----------------------------------------------------------

    def create_pending(
        self, *, founder_id: int, amount_inr: int, currency: str, gateway: str,
        gateway_order_id: str,
    ) -> int:
        payment_id = self.db.execute(
            text(
                "INSERT INTO payments "
                "(founder_id, amount_inr, currency, status, payment_gateway, gateway_order_id) "
                "VALUES (:fid, :amt, :cur, 'pending', :gw, :goid) "
                "RETURNING payment_id"
            ),
            {"fid": founder_id, "amt": amount_inr, "cur": currency, "gw": gateway,
             "goid": gateway_order_id},
        ).scalar()
        self.db.commit()
        return payment_id

    def get_by_gateway_order_id(self, gateway_order_id: str) -> PaymentRecord | None:
        row = self.db.execute(
            text(
                "SELECT payment_id, founder_id, status, gateway_order_id, "
                "       gateway_payment_id, amount_inr, subscription_id "
                "FROM payments WHERE gateway_order_id = :goid"
            ),
            {"goid": gateway_order_id},
        ).mappings().first()
        return _to_record(row)

    def get_by_gateway_payment_id(self, gateway_payment_id: str) -> PaymentRecord | None:
        """The idempotency check: Razorpay retries webhook deliveries, and a
        `gateway_payment_id` already recorded here means this exact payment
        has already been granted -- never grant a plan or credits twice for
        the same payment."""
        row = self.db.execute(
            text(
                "SELECT payment_id, founder_id, status, gateway_order_id, "
                "       gateway_payment_id, amount_inr, subscription_id "
                "FROM payments WHERE gateway_payment_id = :gpid"
            ),
            {"gpid": gateway_payment_id},
        ).mappings().first()
        return _to_record(row)

    def mark_captured(
        self, payment_id: int, *, gateway_payment_id: str, paid_at: datetime,
        subscription_id: int,
    ) -> None:
        self.db.execute(
            text(
                "UPDATE payments SET status = 'success', gateway_payment_id = :gpid, "
                "                    paid_at = :at, subscription_id = :sid "
                "WHERE payment_id = :pid"
            ),
            {"gpid": gateway_payment_id, "at": paid_at, "sid": subscription_id, "pid": payment_id},
        )
        self.db.commit()

    def mark_failed(self, payment_id: int, *, reason: str) -> None:
        self.db.execute(
            text("UPDATE payments SET status = 'failed', failure_reason = :reason "
                 "WHERE payment_id = :pid"),
            {"reason": reason, "pid": payment_id},
        )
        self.db.commit()

    # --- subscriptions + the plan itself ------------------------------------

    def create_subscription(
        self, *, founder_id: int, plan_type: str, amount_inr: int, billing_cycle: str,
        expires_at: datetime, gateway: str,
    ) -> int:
        subscription_id = self.db.execute(
            text(
                "INSERT INTO subscriptions "
                "(founder_id, plan_type, status, billing_cycle, amount_inr, "
                " expires_at, payment_gateway) "
                "VALUES (:fid, :plan, 'active', :cycle, :amt, :exp, :gw) "
                "RETURNING subscription_id"
            ),
            {"fid": founder_id, "plan": plan_type, "cycle": billing_cycle, "amt": amount_inr,
             "exp": expires_at, "gw": gateway},
        ).scalar()
        self.db.commit()
        return subscription_id

    def grant_plan(self, founder_id: int, plan_type: str) -> None:
        """The actual upgrade -- same column `PATCH /admin/users/{id}/subscription`
        writes, so a founder's entitlements read the same way regardless of
        whether an admin or a real payment put them there."""
        self.db.execute(
            text("UPDATE founders SET plan_type = :plan, updated_at = now() "
                 "WHERE founder_id = :fid"),
            {"plan": plan_type, "fid": founder_id},
        )
        self.db.commit()


def _to_record(row) -> PaymentRecord | None:
    if row is None:
        return None
    return PaymentRecord(
        payment_id=row["payment_id"], founder_id=row["founder_id"], status=row["status"],
        gateway_order_id=row["gateway_order_id"], gateway_payment_id=row["gateway_payment_id"],
        amount_inr=row["amount_inr"], subscription_id=row["subscription_id"],
    )
