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


class InvalidCheckoutCallbackError(PaymentError):
    """The browser handed back a checkout callback whose `order_id|payment_id`
    signature does not match the key secret. 401 for the same reason
    InvalidWebhookSignatureError is: it is "this did not come from Razorpay",
    not a malformed field -- and it must never be read as "payment succeeded"."""

    def __init__(self):
        super().__init__("Invalid payment confirmation signature.",
                         status_code=status.HTTP_401_UNAUTHORIZED)


class PaymentNotFoundError(PaymentError):
    """No pending payment of this founder's carries that order id. 404 rather
    than 403 on someone else's order too: a founder poking at order ids must
    not be able to learn which ones exist."""

    def __init__(self):
        super().__init__("We could not find that payment.",
                         status_code=status.HTTP_404_NOT_FOUND)


class SubscriptionPlanNotConfiguredError(PaymentError):
    """No Razorpay Plan id is registered for this tier in this mode.

    503 for the same reason PaymentsNotConfiguredError is: the request was
    fine, the environment is not finished. Distinct from it because the fix is
    different and an operator reading a log needs to know which -- keys are set
    here, but nobody has run the "create the Rs 499 plan and register its id"
    step (guide step 2). Faking a subscription against a guessed plan id would
    charge a founder an amount nobody chose."""

    def __init__(self, plan_name: str):
        super().__init__(
            f"{plan_name} subscriptions are not available yet. Please email info@goxl.in "
            "and we will get you set up.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class SubscriptionAlreadyActiveError(PaymentError):
    """This founder already has a live mandate.

    409, and refused rather than stacked: two mandates means two charges every
    month, and the founder would not find out until their card statement. The
    message names the date their current access runs to so the billing page can
    show a real next step rather than a dead end.

    A plan CHANGE (Plus -> Pro) lands here too, deliberately. Doing it properly
    means cancelling one mandate and starting another with a defensible answer
    for the overlap the founder already paid for, and that is a pricing
    decision rather than a coding one. Refusing is the honest interim: nobody
    is double-charged, and support can cancel and re-subscribe on request."""

    def __init__(self, plan_name: str, access_until=None):
        until = f" Your current access runs to {access_until:%d %b %Y}." if access_until else ""
        super().__init__(
            f"You already have an active {plan_name} subscription.{until} "
            "Cancel it first if you want to move to a different plan.",
            status_code=status.HTTP_409_CONFLICT,
        )


class NoActiveSubscriptionError(PaymentError):
    """Nothing to cancel. 404 rather than 400: from the founder's side the
    thing they asked to act on does not exist."""

    def __init__(self):
        super().__init__("You do not have an active subscription to cancel.",
                         status_code=status.HTTP_404_NOT_FOUND)


class InvalidBillingProfileError(PaymentError):
    """A GSTIN or billing field that cannot be right. 422, and refused at write
    time on purpose -- a malformed GSTIN discovered on an invoice is one the
    customer cannot claim input credit against, and by then the invoice is
    already issued."""

    def __init__(self, reason: str):
        super().__init__(f"Billing details could not be saved: {reason}.", status_code=422)
