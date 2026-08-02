"""Credit persistence seam.

The interface is shaped around ONE atomic primitive -- `apply` -- rather than
separate read-balance / write-balance / append-row calls. If the service could read
the balance, compute, then write, two concurrent admins would interleave and one
update would be lost. Handing the whole read-settle-modify-append to the repository
lets each implementation make it atomic in its own way: an RLock in memory,
`SELECT ... FOR UPDATE` in Postgres.

Both implementations run the *same* lifecycle logic (`app.credits.expiry.settle`)
and the *same* bucket policy (`app.credits.buckets.plan_movements`), so a rule the
hermetic suite proves here is the rule the database path executes.
"""

from __future__ import annotations

import abc
import threading
from datetime import datetime

from app.credits.buckets import plan_movements
from app.credits.errors import InsufficientCreditsError, UserNotFoundError
from app.credits.expiry import CreditBucket, CreditState, settle
from app.credits.models import CreditBalance, CreditOperation, CreditTransaction

SYSTEM_ADMIN_ID = 0


class CreditRepository(abc.ABC):
    @abc.abstractmethod
    def apply(self, user_id: int, *, admin_id: int, operation: CreditOperation,
              requested_amount: int, reason: str, at: datetime) -> CreditTransaction:
        """Atomically: lock, settle expiry/renewal, apply the operation, append the
        ledger rows and update the stored balance. Raises InsufficientCreditsError
        if the result would be negative, leaving no partial write behind."""

    @abc.abstractmethod
    def get_balance(self, user_id: int) -> CreditBalance:
        """Settled total. Must settle before reporting."""

    @abc.abstractmethod
    def list_transactions(self, user_id: int, *, limit: int = 50,
                          offset: int = 0) -> tuple[list[CreditTransaction], int]:
        """Newest first. Returns (page, total). Does not settle -- reading history
        must never mutate it."""


def resolve_delta(operation: CreditOperation, requested: int, current: int) -> int:
    """Signed change an operation implies against a single total.

    Retained for callers that reason about the net effect without buckets (and for
    the original single-balance tests). The buckets themselves are resolved by
    `app.credits.buckets.plan_movements`.
    """
    if operation in (CreditOperation.ADD, CreditOperation.BONUS):
        return requested
    if operation in (CreditOperation.REMOVE, CreditOperation.CONSUME):
        return -requested
    if operation is CreditOperation.SET:
        return requested - current
    raise ValueError(f"unknown operation {operation!r}")


class InMemoryCreditRepository(CreditRepository):
    """Offline double. A single RLock makes `apply` atomic, mirroring the row lock
    the SQL implementation takes.

    The constructor accepts either `{user_id: int}` -- the balance is then treated
    as **bonus**, matching how the migration backfills existing balances -- or
    `{user_id: CreditState}` for tests that exercise the lifecycle.
    """

    def __init__(self, balances: dict[int, int | CreditState] | None = None) -> None:
        self._states: dict[int, CreditState] = {}
        for uid, value in (balances or {}).items():
            self._states[uid] = (value if isinstance(value, CreditState)
                                 else CreditState(bonus=int(value)))
        self._rows: list[CreditTransaction] = []
        self._next_id = 1
        self._lock = threading.RLock()

    # --- helpers ---------------------------------------------------------

    def seed_user(self, user_id: int, balance: int | CreditState = 0) -> None:
        with self._lock:
            self._states[user_id] = (balance if isinstance(balance, CreditState)
                                     else CreditState(bonus=int(balance)))

    def _require(self, user_id: int) -> CreditState:
        if user_id not in self._states:
            raise UserNotFoundError(user_id)
        return self._states[user_id]

    def _append(self, user_id: int, *, admin_id: int, op: CreditOperation, amount: int,
                before: int, after: int, reason: str, at: datetime) -> CreditTransaction:
        tx = CreditTransaction(
            id=self._next_id, user_id=user_id, admin_id=admin_id, type=op,
            amount=amount, balance_before=before, balance_after=after,
            reason=reason, created_at=at)
        self._next_id += 1
        self._rows.append(tx)
        return tx

    def _settle_locked(self, user_id: int, state: CreditState,
                       now: datetime) -> tuple[CreditState, int]:
        settled, steps = settle(state, now)
        for step in steps:
            self._append(user_id, admin_id=SYSTEM_ADMIN_ID,
                         op=CreditOperation(step.type), amount=step.amount,
                         before=step.balance_before, after=step.balance_after,
                         reason=step.reason, at=step.at)
        return settled, len(steps)

    # --- public API ------------------------------------------------------

    def settle_only(self, user_id: int, now: datetime) -> tuple[CreditBalance, int]:
        with self._lock:
            state = self._require(user_id)
            settled, written = self._settle_locked(user_id, state, now)
            self._states[user_id] = settled
            return CreditBalance(user_id=user_id, balance=settled.total), written

    def apply(self, user_id: int, *, admin_id: int, operation: CreditOperation,
              requested_amount: int, reason: str, at: datetime) -> CreditTransaction:
        with self._lock:
            state = self._require(user_id)
            # Marker so a failure can undo settlement too -- see below.
            rows_before = len(self._rows)

            # Lifecycle first -- expired monthly credits are gone before the
            # operation is planned, so they can never be spent.
            settled, _ = self._settle_locked(user_id, state, at)

            try:
                final_state, movements = plan_movements(settled, operation, requested_amount)
            except ValueError as exc:
                if str(exc).startswith("insufficient:"):
                    _, available, wanted = str(exc).split(":")
                    # Roll settlement back with the operation, mirroring the SQL
                    # implementation's single-transaction rollback. Nothing is lost:
                    # `settle` is a pure function of stored state and time, so the
                    # next read or write re-derives exactly the same steps. Keeping
                    # the settlement here instead would make the two implementations
                    # disagree, and the in-memory double would stop being evidence
                    # about production.
                    del self._rows[rows_before:]
                    self._states[user_id] = state
                    raise InsufficientCreditsError(int(available), int(wanted)) from exc
                raise

            running_before, last = settled.total, None
            for _bucket, delta in movements:
                running_after = running_before + delta
                last = self._append(user_id, admin_id=admin_id, op=operation, amount=delta,
                                    before=running_before, after=running_after,
                                    reason=reason, at=at)
                running_before = running_after

            self._states[user_id] = final_state

            if last is None:                     # no-op (e.g. SET to the current total)
                return CreditTransaction(
                    id=0, user_id=user_id, admin_id=admin_id, type=operation, amount=0,
                    balance_before=settled.total, balance_after=final_state.total,
                    reason=reason, created_at=at)

            return CreditTransaction(
                id=last.id, user_id=user_id, admin_id=admin_id, type=operation,
                amount=final_state.total - settled.total,
                balance_before=settled.total, balance_after=final_state.total,
                reason=reason, created_at=at)

    def get_balance(self, user_id: int) -> CreditBalance:
        from datetime import timezone
        with self._lock:
            self._require(user_id)
            balance, _ = self.settle_only(user_id, datetime.now(timezone.utc))
            mine = [r for r in self._rows if r.user_id == user_id]
            return CreditBalance(user_id=user_id, balance=balance.balance,
                                 last_transaction_at=mine[-1].created_at if mine else None)

    def get_state(self, user_id: int) -> CreditState:
        from datetime import timezone
        with self._lock:
            self._require(user_id)
            self.settle_only(user_id, datetime.now(timezone.utc))
            return self._states[user_id]

    def list_transactions(self, user_id: int, *, limit: int = 50,
                          offset: int = 0) -> tuple[list[CreditTransaction], int]:
        with self._lock:
            mine = [r for r in reversed(self._rows) if r.user_id == user_id]
            return mine[offset:offset + limit], len(mine)
