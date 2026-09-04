"""Payment errors. AppError subclasses so the global handler maps them to
consistent JSON and everything fails closed -- same convention as
app/admin/errors.py."""

from fastapi import status

from app.middleware.error_handler import AppError


class PaymentError(AppError):
    """Base for payment failures."""


class PaymentsNotConfiguredError(PaymentError):
    """No Razorpay keys set in this environment. 503, not 500 or a faked
    success -- this is "the feature isn't wired up here", the same shape
    /admin/health reports for an unconfigured component, not a bug."""

    def __init__(self):
        super().__init__("Payments are not configured in this environment.",
                         status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class InvalidCheckoutError(PaymentError):
    def __init__(self, reason: str):
        super().__init__(f"Cannot start checkout: {reason}.", status_code=422)


class InvalidWebhookSignatureError(PaymentError):
    """A webhook payload whose signature does not match. 401: this is an
    authentication failure (is this really Razorpay?), not a validation
    error -- and it must never be treated as "payment succeeded"."""

    def __init__(self):
        super().__init__("Invalid webhook signature.", status_code=status.HTTP_401_UNAUTHORIZED)
