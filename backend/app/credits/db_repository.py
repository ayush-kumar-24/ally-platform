"""DB-backed credit ledger with lifecycle settlement.

The whole file exists to make one sequence atomic:

    BEGIN
      SELECT monthly, bonus, expires_at, renewal_date, allowance
        FROM founders WHERE founder_id = :id FOR UPDATE     -- row lock
      settle(state, now)                 -- pure; from app.credits.expiry
      INSERT one ledger row per settlement step (expire / renew)
      plan_movements(state, operation)   -- pure; from app.credits.buckets
      INSERT one ledger row per bucket movement
      UPDATE founders  (both buckets, dates, and the credits_balance cache)
    COMMIT

Why settlement lives inside the lock
------------------------------------
Settling outside it would let two requests both observe "expiry is due", both append
an `expire` row, and double-count the loss. `FOR UPDATE` serialises them: the second
transaction reads the *already settled* state, `settle` finds nothing due, and it
emits no rows. That is what makes settlement idempotent in practice, not just in
theory -- the purity of `settle` provides the second half.

Any exception rolls back the whole thing, so the ledger can never contain a
settlement row whose balance update did not land (or the reverse).

The expiry engine (app/credits/expiry.py) is used as-is and is not modified here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.credits.buckets import plan_movements
from app.credits.errors import InsufficientCreditsError, UserNotFoundError
from app.credits.expiry import CreditBucket, CreditState, settle
from app.credits.models import CreditBalance, CreditOperation, CreditTransaction
from app.credits.repository import CreditRepository

#: admin_id recorded on rows nobody requested. Settlement is caused by time passing,
#: so attributing it to the admin who happened to trigger the read would be a lie in
#: the audit trail.
SYSTEM_ADMIN_ID = 0

_LOCK_SQL = """
    select monthly_credits, bonus_credits, credits_expires_at,
           credits_renewal_date, monthly_credit_allowance
      from founders
     where founder_id = :uid
       for update
"""

_INSERT_SQL = """
    insert into credit_transactions
        (user_id, admin_id, type, bucket, amount, balance_before,
         balance_after, reason, created_at)
    values (:uid, :aid, :typ, :bucket, :amt, :bef, :aft, :rsn, :at)
    returning id, created_at
"""

_UPDATE_SQL = """
    update founders
       set monthly_credits = :monthly,
           bonus_credits = :bonus,
           credits_expires_at = :expires,
           credits_renewal_date = :renews,
           credits_balance = :total
     where founder_id = :uid
"""


class SqlAlchemyCreditRepository(CreditRepository):
    def __init__(self, db):
        self.db = db

    # --- internals -------------------------------------------------------

    def _lock_state(self, user_id: int) -> CreditState:
        row = self.db.execute(text(_LOCK_SQL), {"uid": user_id}).mappings().first()
        if row is None:
            raise UserNotFoundError(user_id)
        return CreditState(
            monthly=int(row["monthly_credits"] or 0),
            bonus=int(row["bonus_credits"] or 0),
            expires_at=row["credits_expires_at"],
            renewal_date=row["credits_renewal_date"],
            monthly_allowance=int(row["monthly_credit_allowance"] or 0),
        )

    def _write_row(self, user_id: int, *, admin_id: int, op: str, bucket: str,
                   amount: int, before: int, after: int, reason: str, at: datetime):
        return self.db.execute(text(_INSERT_SQL), {
            "uid": user_id, "aid": admin_id, "typ": op, "bucket": bucket,
            "amt": amount, "bef": before, "aft": after, "rsn": reason, "at": at,
        }).mappings().first()

    def _persist(self, user_id: int, state: CreditState) -> None:
        self.db.execute(text(_UPDATE_SQL), {
            "monthly": state.monthly, "bonus": state.bonus,
            "expires": state.expires_at, "renews": state.renewal_date,
            "total": state.total, "uid": user_id,
        })

    def _settle_locked(self, user_id: int, state: CreditState, now: datetime
                       ) -> tuple[CreditState, int]:
        """Run settlement and append its ledger rows. Caller already holds the lock.

        Returns the settled state and the number of rows written (0 when nothing was
        due -- the idempotent case).
        """
        settled, steps = settle(state, now)
        for step in steps:
            self._write_row(
                user_id, admin_id=SYSTEM_ADMIN_ID, op=step.type, bucket=step.bucket.value,
                amount=step.amount, before=step.balance_before, after=step.balance_after,
                reason=step.reason, at=step.at)
        return settled, len(steps)

    # --- public API ------------------------------------------------------

    def settle_only(self, user_id: int, now: datetime) -> tuple[CreditBalance, int]:
        """Settle without applying an operation. Used by reads."""
        try:
            state = self._lock_state(user_id)
            settled, written = self._settle_locked(user_id, state, now)
            if written:
                self._persist(user_id, settled)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return CreditBalance(user_id=user_id, balance=settled.total), written

    def apply(self, user_id: int, *, admin_id: int, operation: CreditOperation,
              requested_amount: int, reason: str, at: datetime) -> CreditTransaction:
        try:
            state = self._lock_state(user_id)

            # 1. Lifecycle first. This is what guarantees expired monthly credits
            #    can never be spent: they are zeroed before the operation is planned.
            settled, _ = self._settle_locked(user_id, state, at)

            # 2. Plan the requested operation against the settled buckets.
            try:
                final_state, movements = plan_movements(settled, operation, requested_amount)
            except ValueError as exc:
                if str(exc).startswith("insufficient:"):
                    _, available, wanted = str(exc).split(":")
                    raise InsufficientCreditsError(int(available), int(wanted)) from exc
                raise

            # 3. One ledger row per bucket touched, chained through the balance.
            running_before = settled.total
            last_row, last_delta, last_bucket = None, 0, CreditBucket.BONUS
            for bucket, delta in movements:
                running_after = running_before + delta
                last_row = self._write_row(
                    user_id, admin_id=admin_id, op=operation.value, bucket=bucket.value,
                    amount=delta, before=running_before, after=running_after,
                    reason=reason, at=at)
                running_before = running_after
                last_delta, last_bucket = delta, bucket

            # A no-op (e.g. SET to the value already held) writes nothing. Report the
            # settled position rather than inventing a zero-amount row.
            if last_row is None:
                self._persist(user_id, final_state)
                self.db.commit()
                return CreditTransaction(
                    id=0, user_id=user_id, admin_id=admin_id, type=operation,
                    amount=0, balance_before=settled.total, balance_after=final_state.total,
                    reason=reason, created_at=at)

            self._persist(user_id, final_state)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return CreditTransaction(
            id=last_row["id"], user_id=user_id, admin_id=admin_id, type=operation,
            # `amount` on the returned DTO is the net change, so callers that show
            # "you were charged N" don't have to re-add the per-bucket rows.
            amount=final_state.total - settled.total,
            balance_before=settled.total, balance_after=final_state.total,
            reason=reason, created_at=last_row["created_at"],
        )

    def get_balance(self, user_id: int) -> CreditBalance:
        """Settle, then report. A balance read that skipped settlement could show
        credits that have already expired -- and the user would try to spend them."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        balance, _ = self.settle_only(user_id, now)
        row = self.db.execute(
            text("""select (select max(created_at) from credit_transactions
                             where user_id = :uid) as last_at"""),
            {"uid": user_id}).mappings().first()
        return CreditBalance(user_id=user_id, balance=balance.balance,
                             last_transaction_at=row["last_at"] if row else None)

    def get_state(self, user_id: int) -> CreditState:
        """Settled bucket detail -- for the admin UI, which shows monthly and bonus
        separately alongside the renewal date."""
        from datetime import timezone
        self.settle_only(user_id, datetime.now(timezone.utc))
        row = self.db.execute(text("""
            select monthly_credits, bonus_credits, credits_expires_at,
                   credits_renewal_date, monthly_credit_allowance
              from founders where founder_id = :uid"""),
            {"uid": user_id}).mappings().first()
        if row is None:
            raise UserNotFoundError(user_id)
        return CreditState(
            monthly=int(row["monthly_credits"] or 0),
            bonus=int(row["bonus_credits"] or 0),
            expires_at=row["credits_expires_at"],
            renewal_date=row["credits_renewal_date"],
            monthly_allowance=int(row["monthly_credit_allowance"] or 0))

    def list_transactions(self, user_id: int, *, limit: int = 50,
                          offset: int = 0) -> tuple[list[CreditTransaction], int]:
        """Read-only: deliberately does NOT settle.

        Settlement writes rows, and paging through history must not mutate it --
        clicking "next page" should never change what the ledger contains.
        """
        total = self.db.execute(
            text("select count(*) from credit_transactions where user_id = :uid"),
            {"uid": user_id}).scalar() or 0
        rows = self.db.execute(text("""
            select id, user_id, admin_id, type, bucket, amount, balance_before,
                   balance_after, reason, created_at
              from credit_transactions
             where user_id = :uid
             order by created_at desc, id desc
             limit :lim offset :off"""),
            {"uid": user_id, "lim": limit, "off": offset}).mappings().all()
        return [_to_domain(r) for r in rows], int(total)


def _to_domain(row) -> CreditTransaction:
    return CreditTransaction(
        id=row["id"], user_id=row["user_id"], admin_id=row["admin_id"],
        type=CreditOperation(row["type"]), amount=row["amount"],
        balance_before=row["balance_before"], balance_after=row["balance_after"],
        reason=row["reason"], created_at=row["created_at"])
