"""Domain DTOs for the credit ledger.

The ledger is the source of truth. `founders.credits_balance` is a cache kept in
step inside the same transaction -- see CreditService for why both exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CreditOperation(str, Enum):
    """What the admin asked for. Distinct from the *effect*: SET can raise or lower
    a balance, so the requested operation is recorded rather than inferred from the
    sign of the delta."""

    ADD = "add"
    REMOVE = "remove"
    SET = "set"
    BONUS = "bonus"          # "transfer bonus" -- an additive grant, tagged for reporting

    # Non-admin operations. CONSUME is the application spending a user's credits;
    # EXPIRE and RENEW are written by settlement, never requested by anyone. They
    # are ledger types rather than a separate table so the balance history stays a
    # single chain -- a row's balance_before always equals the previous row's
    # balance_after, whoever caused it.
    CONSUME = "consume"
    EXPIRE = "expire"
    RENEW = "renew"


#: Operations an admin may request through the API. EXPIRE/RENEW are excluded --
#: they are consequences of time passing, not actions anyone takes.
ADMIN_OPERATIONS = (CreditOperation.ADD, CreditOperation.REMOVE,
                    CreditOperation.SET, CreditOperation.BONUS)


@dataclass(frozen=True)
class CreditTransaction:
    """One immutable ledger row.

    `balance_before` / `balance_after` are stored rather than derived: it makes each
    row independently auditable and makes a drifted cache detectable by comparing
    the newest row's balance_after against founders.credits_balance.
    """

    id: int
    user_id: int
    admin_id: int
    type: CreditOperation
    amount: int              # the delta actually applied (signed: negative = removed)
    balance_before: int
    balance_after: int
    reason: str
    created_at: datetime


@dataclass(frozen=True)
class CreditBalance:
    user_id: int
    balance: int
    last_transaction_at: datetime | None = None
