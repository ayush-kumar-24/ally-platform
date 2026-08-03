"""Credit ledger -- append-only record of every credit movement.

Public surface (import from here, not from submodules):

    CreditTransaction / CreditBalance / CreditOperation   frozen domain DTOs
    CreditService / build_credit_service()                business rules
    CreditRepository / InMemoryCreditRepository           persistence seam
    errors                                                -> precise HTTP statuses

Balances are never overwritten in place by callers: every change goes through
CreditService.adjust, which appends a ledger row and updates the cached balance
inside one transaction.
"""

from app.credits.errors import (
    CreditError,
    InsufficientCreditsError,
    InvalidCreditAmountError,
    MissingReasonError,
    UserNotFoundError,
)
from app.credits.models import CreditBalance, CreditOperation, CreditTransaction
from app.credits.repository import (
    CreditRepository,
    InMemoryCreditRepository,
    resolve_delta,
)
from app.credits.service import CreditService, build_credit_service

__all__ = [
    "CreditBalance",
    "CreditError",
    "CreditOperation",
    "CreditRepository",
    "CreditService",
    "CreditTransaction",
    "InMemoryCreditRepository",
    "InsufficientCreditsError",
    "InvalidCreditAmountError",
    "MissingReasonError",
    "UserNotFoundError",
    "build_credit_service",
    "resolve_delta",
]
