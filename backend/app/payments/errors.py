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


class PaymentGatewayUnavailableError(PaymentError):
    """Razorpay refused or failed to create the order. 502, not 500: the
    request itself was fine and nothing in this backend broke -- the upstream
    provider said no (or nothing). Without this, the gateway's own
    PaymentGatewayError (a plain Exception, deliberately -- app.payments.gateway
    knows nothing about HTTP responses) fell through to the unhandled-exception
    handler and the founder read "Something went wrong. We've logged it." for
    what is, from where they sit, "the payment provider is not answering right
    now". The message stays founder-facing on purpose: the *reason* (a 401 from
    a wrong key, a 400 naming a field) is in the log line, never in the body."""

    def __init__(self):
        super().__init__(
            "Our payment provider couldn't create this order. Please try again in a "
            "moment, or email info@goxl.in if it keeps happening.",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class InvalidCheckoutError(PaymentError):
    def __init__(self, reason: str):
        super().__init__(f"Cannot start checkout: {reason}.", status_code=422)


class InvalidWebhookSignatureError(PaymentError):
    """A webhook payload whose signature does not match. 401: this is an
    authentication failure (is this really Razorpay?), not a validation
    error -- and it must never be treated as "payment succeeded"."""

    def __init__(self):
        super().__init__("Invalid webhook signature.", status_code=status.HTTP_401_UNAUTHORIZED)
