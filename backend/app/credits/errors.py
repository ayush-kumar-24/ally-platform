"""Errors for the credit ledger. Extend AppError so failures map to HTTP statuses."""

from app.middleware.error_handler import AppError


class CreditError(AppError):
    """Base for credit failures."""


class InsufficientCreditsError(CreditError):
    """The operation would drive the balance below zero.

    409 rather than 422: the request is well-formed, it just conflicts with the
    account's current state -- and that state may differ by the time it is retried.
    """

    def __init__(self, balance: int, requested: int):
        super().__init__(
            f"Insufficient credits: balance is {balance}, "
            f"but the operation would remove {requested}.",
            status_code=409,
        )


class InvalidCreditAmountError(CreditError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid credit amount: {reason}.", status_code=422)


class MissingReasonError(CreditError):
    """Every credit movement must say why.

    A ledger entry without a reason is unauditable -- six months later nobody can
    tell a support goodwill grant from a mistake, so the write is refused.
    """

    def __init__(self) -> None:
        super().__init__("A reason is required for every credit transaction.", status_code=422)


class UserNotFoundError(CreditError):
    def __init__(self, user_id: int):
        super().__init__(f"No user {user_id} exists.", status_code=404)
