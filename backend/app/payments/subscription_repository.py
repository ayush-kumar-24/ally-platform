"""Raw-SQL reads/writes for the recurring half: `subscriptions`,
`invoices` and the `razorpay_plans` id map.

Same style as app/payments/repository.py and app/admin/users_db_repository.py
-- parameterised `text()` with explicit columns, no ORM models for these
tables.

One rule runs through the whole module: **a row here mirrors what Razorpay
said, it does not decide anything.** `paid_count`, `current_period_end` and
`next_charge_at` are copied off the subscription entity rather than computed,
because a number this codebase derived would drift the first time a webhook
was missed, and the founder's next charge date would then be a guess printed
as a fact. The one column that is genuinely ours is `access_until` -- see
SubscriptionService for how it is set and why.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


def epoch_to_dt(value: int | None) -> datetime | None:
    """Razorpay timestamps are epoch seconds. Converted in exactly one place:
    a 0 or a None must become None, not 1970 -- a period end of 1970 silently
    means "access expired 56 years ago" to every query that reads it."""
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


@dataclass(frozen=True)
class SubscriptionRecord:
    subscription_id: int
    founder_id: int
    plan_type: str
    status: str
    gateway_subscription_id: str | None
    razorpay_plan_id: str | None
    amount_inr: int
    paid_count: int
    current_period_start: datetime | None
    current_period_end: datetime | None
    next_charge_at: datetime | None
    access_until: datetime | None
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    ended_at: datetime | None
    activated_at: datetime | None
    started_at: datetime | None
    billing_cycle: str | None

    @property
    def is_recurring(self) -> bool:
        return self.billing_cycle == "monthly" and self.gateway_subscription_id is not None


#: The statuses that mean "this mandate is still live at Razorpay" -- it may
#: charge again, and the founder should see it as their current subscription.
#: `pending` is in here on purpose: a renewal that failed is being retried by
#: Razorpay, and the founder has not lost their plan yet (see
#: SUBSCRIPTION_GRACE_DAYS).
LIVE_STATUSES = ("created", "authenticated", "active", "pending", "halted")

#: Narrower: statuses where money has actually been taken at least once.
PAID_STATUSES = ("active", "pending", "halted")

_COLUMNS = """
    subscription_id, founder_id, plan_type, status, gateway_subscription_id,
    razorpay_plan_id, amount_inr, paid_count, current_period_start,
    current_period_end, next_charge_at, access_until, cancel_at_period_end,
    cancelled_at, ended_at, activated_at, started_at, billing_cycle
"""


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- the Razorpay Plan id map ------------------------------------------

    def active_plan_id(self, tier: str, mode: str) -> str | None:
        """The Razorpay Plan id new subscriptions for `tier` are created on.

        Scoped by mode so a backend running test keys can never create a
        subscription against a live plan. Returns None when nobody has
        registered one yet -- the caller turns that into a 503 rather than
        guessing an id.
        """
        return self.db.execute(
            text("SELECT razorpay_plan_id FROM razorpay_plans "
                 "WHERE tier = :tier AND mode = :mode AND is_active LIMIT 1"),
            {"tier": tier, "mode": mode},
        ).scalar()

    def list_plan_map(self, mode: str | None = None) -> list[dict]:
        rows = self.db.execute(
            text("SELECT plan_map_id, tier, mode, razorpay_plan_id, amount_inr, "
                 "       billing_period, billing_interval, is_active, notes, created_at "
                 "FROM razorpay_plans "
                 # CAST, not a bare :mode -- Postgres cannot infer the type of
                 # a NULL parameter compared only to itself, and this query is
                 # called with mode=None to mean "every mode".
                 "WHERE (CAST(:mode AS text) IS NULL OR mode = :mode) "
                 "ORDER BY is_active DESC, tier, created_at DESC"),
            {"mode": mode},
        ).mappings().all()
        return [dict(r) for r in rows]

    def register_plan(self, *, tier: str, mode: str, razorpay_plan_id: str,
                      amount_inr: int, billing_period: str = "monthly",
                      billing_interval: int = 1, notes: str | None = None) -> int:
        """Record a Razorpay Plan id as THE one for this tier and mode.

        Deactivates whatever held that slot first, in the same transaction:
        the unique index only permits one active row per (tier, mode), so
        doing this in two commits would leave a window where a subscription
        could be created against a plan that is on its way out, or none at all.
        Superseded rows are kept, not deleted -- the founders already billed on
        them still need their subscription's plan id to resolve to something.
        """
        self.db.execute(
            text("UPDATE razorpay_plans SET is_active = false, updated_at = now() "
                 "WHERE tier = :tier AND mode = :mode AND is_active"),
            {"tier": tier, "mode": mode},
        )
        plan_map_id = self.db.execute(
            text("INSERT INTO razorpay_plans "
                 "(tier, mode, razorpay_plan_id, amount_inr, billing_period, "
                 " billing_interval, is_active, notes) "
                 "VALUES (:tier, :mode, :rpid, :amt, :period, :interval, true, :notes) "
                 # Re-registering the SAME plan id reactivates its row instead
                 # of raising. That happens for real: an admin re-runs the
                 # registration after a superseding plan turned out to be
                 # wrong, and "this id is already known" is not an error worth
                 # a 500 -- it is the outcome they asked for. A DIFFERENT id
                 # for the same tier still supersedes, via the UPDATE above.
                 "ON CONFLICT (razorpay_plan_id) DO UPDATE SET "
                 "  tier = EXCLUDED.tier, mode = EXCLUDED.mode, "
                 "  amount_inr = EXCLUDED.amount_inr, is_active = true, "
                 "  notes = COALESCE(EXCLUDED.notes, razorpay_plans.notes), "
                 "  updated_at = now() "
                 "RETURNING plan_map_id"),
            {"tier": tier, "mode": mode, "rpid": razorpay_plan_id, "amt": amount_inr,
             "period": billing_period, "interval": billing_interval, "notes": notes},
        ).scalar()
        self.db.commit()
        return plan_map_id

    # --- subscriptions -----------------------------------------------------

    def get_by_gateway_id(self, gateway_subscription_id: str) -> SubscriptionRecord | None:
        row = self.db.execute(
            text(f"SELECT {_COLUMNS} FROM subscriptions "
                 "WHERE gateway_subscription_id = :gsid"),
            {"gsid": gateway_subscription_id},
        ).mappings().first()
        return _to_record(row)

    def get_by_id(self, subscription_id: int) -> SubscriptionRecord | None:
        row = self.db.execute(
            text(f"SELECT {_COLUMNS} FROM subscriptions WHERE subscription_id = :sid"),
            {"sid": subscription_id},
        ).mappings().first()
        return _to_record(row)

    def live_for_founder(self, founder_id: int) -> SubscriptionRecord | None:
        """The founder's current recurring subscription, if any.

        Ordered newest first and limited to one: the unique index on
        `gateway_subscription_id` stops duplicates of the SAME mandate, but a
        founder who cancelled last year and resubscribed legitimately has two
        rows, and the live one is the recent one.
        """
        placeholders = ", ".join(f"'{s}'" for s in LIVE_STATUSES)
        row = self.db.execute(
            text(f"SELECT {_COLUMNS} FROM subscriptions "
                 "WHERE founder_id = :fid AND gateway_subscription_id IS NOT NULL "
                 f"  AND status IN ({placeholders}) "
                 "ORDER BY started_at DESC, subscription_id DESC LIMIT 1"),
            {"fid": founder_id},
        ).mappings().first()
        return _to_record(row)

    def latest_for_founder(self, founder_id: int) -> SubscriptionRecord | None:
        """The most recent subscription of any status -- what the billing page
        shows a founder who has cancelled and is running out their paid time."""
        row = self.db.execute(
            text(f"SELECT {_COLUMNS} FROM subscriptions WHERE founder_id = :fid "
                 "ORDER BY started_at DESC, subscription_id DESC LIMIT 1"),
            {"fid": founder_id},
        ).mappings().first()
        return _to_record(row)

    def create_pending(self, *, founder_id: int, plan_type: str, amount_inr: int,
                       gateway_subscription_id: str, razorpay_plan_id: str,
                       status: str, gateway: str = "razorpay") -> int:
        """The row that exists between "founder clicked Subscribe" and "Razorpay
        charged them".

        `access_until` is deliberately NULL and the status is Razorpay's own
        pre-payment one: this row grants nothing. It exists so that when the
        webhook arrives -- possibly before the founder's browser gets back to
        us -- there is already something to attach it to, keyed by the
        subscription id Razorpay will quote.
        """
        subscription_id = self.db.execute(
            text("INSERT INTO subscriptions "
                 "(founder_id, plan_type, status, billing_cycle, amount_inr, "
                 " payment_gateway, gateway_subscription_id, razorpay_plan_id) "
                 "VALUES (:fid, :plan, :status, 'monthly', :amt, :gw, :gsid, :rpid) "
                 "RETURNING subscription_id"),
            {"fid": founder_id, "plan": plan_type, "status": status, "amt": amount_inr,
             "gw": gateway, "gsid": gateway_subscription_id, "rpid": razorpay_plan_id},
        ).scalar()
        self.db.commit()
        return subscription_id

    def sync_from_entity(self, subscription_id: int, *, status: str | None = None,
                         paid_count: int | None = None,
                         current_period_start: datetime | None = None,
                         current_period_end: datetime | None = None,
                         next_charge_at: datetime | None = None,
                         access_until: datetime | None = None,
                         activated_at: datetime | None = None,
                         cancelled_at: datetime | None = None,
                         ended_at: datetime | None = None,
                         cancel_at_period_end: bool | None = None,
                         commit: bool = True) -> None:
        """Mirror whatever the caller learned from Razorpay onto the row.

        Every argument is optional and a None means "leave it alone", not
        "clear it" -- COALESCE in the SQL, not a Python-side merge. A webhook
        that carries only a status must not blank out the period dates a
        previous one established; that is how a founder's next-charge date
        vanishes from the billing page.

        `access_until` is the one exception in spirit: it is still only written
        when passed, but the caller passes it whenever it changes, including
        backwards (halting truncates it to now).
        """
        self.db.execute(
            text("UPDATE subscriptions SET "
                 "  status = COALESCE(:status, status), "
                 "  paid_count = COALESCE(:paid_count, paid_count), "
                 "  current_period_start = COALESCE(:cps, current_period_start), "
                 "  current_period_end = COALESCE(:cpe, current_period_end), "
                 "  next_charge_at = COALESCE(:nca, next_charge_at), "
                 "  access_until = COALESCE(:au, access_until), "
                 "  activated_at = COALESCE(:act, activated_at), "
                 "  cancelled_at = COALESCE(:canc, cancelled_at), "
                 "  ended_at = COALESCE(:ended, ended_at), "
                 "  cancel_at_period_end = COALESCE(:cape, cancel_at_period_end), "
                 "  updated_at = now() "
                 "WHERE subscription_id = :sid"),
            {"status": status, "paid_count": paid_count, "cps": current_period_start,
             "cpe": current_period_end, "nca": next_charge_at, "au": access_until,
             "act": activated_at, "canc": cancelled_at, "ended": ended_at,
             "cape": cancel_at_period_end, "sid": subscription_id},
        )
        if commit:
            self.db.commit()

    def set_access_until(self, subscription_id: int, access_until: datetime | None,
                         *, commit: bool = True) -> None:
        """Write `access_until` unconditionally, including to NULL or to a time
        in the past. Separate from sync_from_entity because that method's
        COALESCE contract cannot express "shorten this" -- and shortening is
        exactly what halting a subscription has to do."""
        self.db.execute(
            text("UPDATE subscriptions SET access_until = :au, updated_at = now() "
                 "WHERE subscription_id = :sid"),
            {"au": access_until, "sid": subscription_id},
        )
        if commit:
            self.db.commit()

    def mark_expired(self, subscription_id: int, *, at: datetime) -> None:
        self.db.execute(
            text("UPDATE subscriptions SET status = 'expired', ended_at = COALESCE(ended_at, :at), "
                 "    updated_at = now() WHERE subscription_id = :sid"),
            {"at": at, "sid": subscription_id},
        )

    def find_lapsed(self, *, now: datetime, limit: int = 200) -> list[SubscriptionRecord]:
        """Subscriptions whose paid access has run out but whose founder is
        still on a paid tier.

        The join to `founders` is what keeps this sweep from fighting the admin
        panel: a founder an admin put on Pro by hand has no subscription row,
        so they never appear here. And a founder whose old subscription lapsed
        but who has since started a NEW live one is excluded by the NOT EXISTS
        -- otherwise resubscribing would be undone by the next sweep.
        """
        live = ", ".join(f"'{s}'" for s in LIVE_STATUSES)
        rows = self.db.execute(
            text(f"SELECT {_COLUMNS} FROM subscriptions s "
                 "WHERE s.access_until IS NOT NULL AND s.access_until < :now "
                 "  AND s.status <> 'expired' "
                 "  AND EXISTS (SELECT 1 FROM founders f "
                 "              WHERE f.founder_id = s.founder_id "
                 "                AND f.plan_type = s.plan_type "
                 "                AND f.plan_type <> 'free') "
                 "  AND NOT EXISTS (SELECT 1 FROM subscriptions s2 "
                 "                  WHERE s2.founder_id = s.founder_id "
                 "                    AND s2.subscription_id <> s.subscription_id "
                 f"                    AND s2.status IN ({live}) "
                 "                    AND (s2.access_until IS NULL "
                 "                         OR s2.access_until >= :now)) "
                 "ORDER BY s.access_until LIMIT :limit"),
            {"now": now, "limit": limit},
        ).mappings().all()
        return [_to_record(r) for r in rows]

    # --- invoices ----------------------------------------------------------

    def upsert_invoice(self, *, founder_id: int, gateway_invoice_id: str,
                       amount_inr, total_amount_inr, status: str,
                       subscription_id: int | None = None, payment_id: int | None = None,
                       gateway_order_id: str | None = None,
                       gateway_payment_id: str | None = None,
                       gateway_subscription_id: str | None = None,
                       invoice_number: str | None = None,
                       tax_amount_inr=None, currency: str = "INR",
                       invoice_url: str | None = None,
                       issued_at: datetime | None = None, paid_at: datetime | None = None,
                       due_at: datetime | None = None, commit: bool = True) -> int:
        """Idempotent on `gateway_invoice_id`: Razorpay retries `invoice.paid`
        the same way it retries `payment.captured`, and a founder must not end
        up with the same receipt listed twice.

        ON CONFLICT DO UPDATE rather than DO NOTHING because an invoice
        legitimately changes -- issued, then paid -- and the second delivery is
        the one carrying `paid_at` and the payment id.
        """
        invoice_id = self.db.execute(
            text("INSERT INTO invoices "
                 "(founder_id, subscription_id, payment_id, gateway_invoice_id, "
                 " gateway_order_id, gateway_payment_id, gateway_subscription_id, "
                 " invoice_number, amount_inr, tax_amount_inr, total_amount_inr, "
                 " currency, status, invoice_url, issued_at, paid_at, due_at) "
                 "VALUES (:fid, :sid, :pid, :giid, :goid, :gpid, :gsid, :num, :amt, "
                 "        :tax, :total, :cur, :status, :url, :issued, :paid, :due) "
                 "ON CONFLICT (gateway_invoice_id) DO UPDATE SET "
                 "  subscription_id = COALESCE(EXCLUDED.subscription_id, invoices.subscription_id), "
                 "  payment_id = COALESCE(EXCLUDED.payment_id, invoices.payment_id), "
                 "  gateway_payment_id = COALESCE(EXCLUDED.gateway_payment_id, "
                 "                                invoices.gateway_payment_id), "
                 "  invoice_number = COALESCE(EXCLUDED.invoice_number, invoices.invoice_number), "
                 "  tax_amount_inr = COALESCE(EXCLUDED.tax_amount_inr, invoices.tax_amount_inr), "
                 "  status = EXCLUDED.status, "
                 "  invoice_url = COALESCE(EXCLUDED.invoice_url, invoices.invoice_url), "
                 "  paid_at = COALESCE(EXCLUDED.paid_at, invoices.paid_at), "
                 "  updated_at = now() "
                 "RETURNING invoice_id"),
            {"fid": founder_id, "sid": subscription_id, "pid": payment_id,
             "giid": gateway_invoice_id, "goid": gateway_order_id, "gpid": gateway_payment_id,
             "gsid": gateway_subscription_id, "num": invoice_number, "amt": amount_inr,
             "tax": tax_amount_inr, "total": total_amount_inr, "cur": currency,
             "status": status, "url": invoice_url, "issued": issued_at, "paid": paid_at,
             "due": due_at},
        ).scalar()
        if commit:
            self.db.commit()
        return invoice_id

    def list_invoices(self, founder_id: int, *, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            text("SELECT invoice_id, gateway_invoice_id, invoice_number, amount_inr, "
                 "       tax_amount_inr, total_amount_inr, currency, status, invoice_url, "
                 "       issued_at, paid_at, due_at "
                 "FROM invoices WHERE founder_id = :fid "
                 "ORDER BY COALESCE(issued_at, created_at) DESC LIMIT :limit"),
            {"fid": founder_id, "limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    # --- payment rows for recurring charges --------------------------------

    def record_subscription_payment(
        self, *, founder_id: int, subscription_id: int, amount_inr, currency: str,
        gateway_payment_id: str, gateway_order_id: str | None,
        gateway_subscription_id: str, gateway_invoice_id: str | None,
        plan_tier: str, paid_at: datetime, commit: bool = True,
    ) -> int | None:
        """A renewal charge, written straight to `payments` as succeeded.

        Unlike a one-time checkout there is no pending row to update: nobody
        opened a checkout, Razorpay simply charged the mandate and told us. The
        row is created already-captured because that is the only state it was
        ever in from our side.

        ON CONFLICT DO NOTHING on `gateway_payment_id` (unique index, migration
        e8a5c31d7f42) makes a redelivered `subscription.charged` a no-op at the
        database rather than at the service -- returning None, which the caller
        reads as "already recorded, do not grant again".
        """
        return self.db.execute(
            text("INSERT INTO payments "
                 "(founder_id, subscription_id, amount_inr, currency, status, "
                 " payment_gateway, gateway_payment_id, gateway_order_id, "
                 " gateway_subscription_id, gateway_invoice_id, plan_tier, paid_at) "
                 "VALUES (:fid, :sid, :amt, :cur, 'success', 'razorpay', :gpid, :goid, "
                 "        :gsid, :giid, :tier, :at) "
                 # The WHERE repeats the index's own predicate. The unique index
                 # on payments.gateway_payment_id is PARTIAL (it excludes NULLs,
                 # which the one-time path writes before a payment is captured),
                 # and Postgres will not match a partial index as a conflict
                 # target unless the inference clause carries the same predicate
                 # -- without it this raises "no unique or exclusion constraint
                 # matching the ON CONFLICT specification" on every charge.
                 "ON CONFLICT (gateway_payment_id) WHERE gateway_payment_id IS NOT NULL "
                 "DO NOTHING "
                 "RETURNING payment_id"),
            {"fid": founder_id, "sid": subscription_id, "amt": amount_inr, "cur": currency,
             "gpid": gateway_payment_id, "goid": gateway_order_id,
             "gsid": gateway_subscription_id, "giid": gateway_invoice_id,
             "tier": plan_tier, "at": paid_at},
        ).scalar()

    def list_payments(self, founder_id: int, *, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            text("SELECT payment_id, amount_inr, currency, status, gateway_payment_id, "
                 "       gateway_order_id, gateway_subscription_id, gateway_invoice_id, "
                 "       plan_tier, failure_reason, paid_at, refunded_at, created_at "
                 "FROM payments WHERE founder_id = :fid "
                 "ORDER BY created_at DESC LIMIT :limit"),
            {"fid": founder_id, "limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]


def _to_record(row) -> SubscriptionRecord | None:
    if row is None:
        return None
    return SubscriptionRecord(
        subscription_id=row["subscription_id"], founder_id=row["founder_id"],
        plan_type=row["plan_type"], status=row["status"],
        gateway_subscription_id=row["gateway_subscription_id"],
        razorpay_plan_id=row["razorpay_plan_id"],
        amount_inr=int(row["amount_inr"] or 0), paid_count=int(row["paid_count"] or 0),
        current_period_start=row["current_period_start"],
        current_period_end=row["current_period_end"],
        next_charge_at=row["next_charge_at"], access_until=row["access_until"],
        cancel_at_period_end=bool(row["cancel_at_period_end"]),
        cancelled_at=row["cancelled_at"], ended_at=row["ended_at"],
        activated_at=row["activated_at"], started_at=row["started_at"],
        billing_cycle=row["billing_cycle"],
    )
