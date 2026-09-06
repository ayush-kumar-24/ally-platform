"""Coupon errors. AppError subclasses so the global handler maps them to the
same JSON shape as everything else -- same convention as app/payments/errors.py.

Every message here is written for the founder staring at the checkout page, and
each one says which of the several ways a code can fail actually happened. A
single "invalid code" for all of them turns a fixable mistake (a typo, a code
meant for another plan) into a dead end, and it is the sort of thing that
generates support mail rather than payments.
"""

from app.middleware.error_handler import AppError


class CouponError(AppError):
    """Base for coupon failures. 422: the request was well-formed, the code
    just does not apply -- not a bug, and not something to retry unchanged."""

    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class CouponNotFoundError(CouponError):
    def __init__(self, code: str):
        super().__init__(f"We don't recognise the code {code}. Check the spelling and try again.")


class CouponExpiredError(CouponError):
    def __init__(self, until):
        super().__init__(f"That code expired on {until:%-d %B %Y}.")


class CouponNotYetValidError(CouponError):
    def __init__(self, start):
        super().__init__(f"That code isn't active until {start:%-d %B %Y}.")


class CouponInactiveError(CouponError):
    def __init__(self):
        super().__init__("That code is no longer available.")


class CouponFullyRedeemedError(CouponError):
    """The "first 100" case, once 100 people have taken it."""

    def __init__(self):
        super().__init__("That code has been fully claimed. You just missed it.")


class CouponAlreadyUsedError(CouponError):
    def __init__(self):
        super().__init__("You've already used that code.")


class CouponNotValidForPlanError(CouponError):
    def __init__(self, plan_name: str):
        super().__init__(f"That code can't be used on the {plan_name} plan.")


class CouponNotApplicableError(CouponError):
    """A free plan needs no checkout, so it needs no coupon either."""

    def __init__(self):
        super().__init__("That plan is free -- no code needed.")
