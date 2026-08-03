"""CreditService -- validation and policy over the ledger.

The atomicity lives in the repository (see db_repository.apply); this layer owns the
rules that hold regardless of storage:

* Amounts must be whole and non-negative. A "remove -50" would be an add in
  disguise, which would make the ledger's `type` column lie about what happened.
* Every transaction needs a reason. An unexplained credit movement is unauditable.
* SET is allowed to be 0 (zeroing a balance is legitimate); ADD/REMOVE/BONUS of 0
  are refused because they would append a no-op row that only adds noise.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.credits.errors import InvalidCreditAmountError, MissingReasonError
from app.credits.models import CreditBalance, CreditOperation, CreditTransaction
from app.credits.repository import CreditRepository

MAX_AMOUNT = 1_000_000          # sanity ceiling: a typo shouldn't grant a fortune
MAX_REASON_LENGTH = 500


class CreditService:
    def __init__(self, repository: CreditRepository, *,
                 clock: Callable[[], datetime] | None = None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def adjust(self, user_id: int, *, admin_id: int, operation: CreditOperation,
               amount: int, reason: str) -> CreditTransaction:
        """Apply a credit operation. Returns the ledger row (which carries the
        updated balance in `balance_after`)."""
        self._validate_amount(operation, amount)
        cleaned = self._validate_reason(reason)
        return self.repository.apply(
            user_id, admin_id=admin_id, operation=operation,
            requested_amount=amount, reason=cleaned, at=self._now())

    def get_balance(self, user_id: int) -> CreditBalance:
        return self.repository.get_balance(user_id)

    def list_transactions(self, user_id: int, *, limit: int = 50, offset: int = 0):
        return self.repository.list_transactions(user_id, limit=limit, offset=offset)

    # --- validation -------------------------------------------------------

    @staticmethod
    def _validate_amount(operation: CreditOperation, amount: int) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise InvalidCreditAmountError("amount must be a whole number")
        if amount < 0:
            raise InvalidCreditAmountError(
                "amount must not be negative -- use the REMOVE operation instead")
        if amount == 0 and operation is not CreditOperation.SET:
            raise InvalidCreditAmountError(f"{operation.value} of 0 would do nothing")
        if amount > MAX_AMOUNT:
            raise InvalidCreditAmountError(f"amount may not exceed {MAX_AMOUNT:,}")

    @staticmethod
    def _validate_reason(reason: str) -> str:
        cleaned = (reason or "").strip()
        if not cleaned:
            raise MissingReasonError()
        if len(cleaned) > MAX_REASON_LENGTH:
            raise InvalidCreditAmountError(
                f"reason may not exceed {MAX_REASON_LENGTH} characters")
        return cleaned


def build_credit_service(repository: CreditRepository | None = None, *,
                         clock: Callable[[], datetime] | None = None) -> CreditService:
    from app.credits.repository import InMemoryCreditRepository

    return CreditService(repository or InMemoryCreditRepository(), clock=clock)
