"""PaymentService -- start_checkout, confirm_checkout and handle_webhook.

Two things can cause a grant, and both settle the question with Razorpay
rather than with the browser:

  - `handle_webhook` -- Razorpay tells us, server-to-server, signed with the
    webhook secret. Authoritative, and the only path that works when the
    founder closes the tab, but it arrives when it arrives: delivery is
    Razorpay's to schedule and routinely runs tens of seconds behind the
    founder staring at "activating".
  - `confirm_checkout` -- the founder's tab says "Razorpay's handler fired",
    and this service goes and ASKS Razorpay whether that is true (a signature
    check on the callback, then a read of the payment entity under the key
    secret). The browser is the trigger, never the evidence: a forged call
    fails the signature, and one that somehow did not would still be answered
    by a payment Razorpay reports as uncaptured.

What must never exist is a third path where the browser's claim alone grants
anything. Both of these end in the same `_grant_for_captured` -- idempotent by
`gateway_payment_id`, so whichever arrives second is a no-op and a plan is
never granted, or credits added, twice.
"""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any

from app.core.logger import logger
from app.coupons.service import CouponService
from app.credits.models import CreditOperation
from app.credits.service import CreditService
from app.payments.errors import (
    InvalidCheckoutCallbackError,
    InvalidCheckoutError,
    PaymentNotFoundError,
    InvalidWebhookSignatureError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
)
from app.payments.billing import parse_billing
from app.payments.gateway import PaymentGateway, PaymentGatewayError
from app.payments.models import CheckoutSession, WebhookOutcome, WebhookResult
from app.payments.repository import PaymentRepository
from app.plans.catalog import PLANS, PlanTier

_CURRENCY = "INR"


def _one_month_after(start: datetime) -> datetime:
    """The same day of the next month, clamped to that month's length.

    A calendar month, not the flat 30 days this used to add. Every plan is sold
    as monthly, and a founder who pays on the 9th expects the 9th -- 30 days
    drifts a little further backwards every cycle (31 Jan + 30d lands on 2 Mar),
    so within a year the renewal date no longer resembles the purchase date.

    Clamping is what makes the 29th, 30th and 31st safe: 31 January renews on
    28 February (29th in a leap year), not on a date that does not exist.
    """
    year = start.year + (start.month // 12)
    month = start.month % 12 + 1
    last_day = monthrange(year, month)[1]
    return start.replace(year=year, month=month, day=min(start.day, last_day))

# Credit grants triggered by a real payment are not an admin action -- same
# system-initiated sentinel app/plans/service.py and app/plans/reconciliation.py
# already use for a non-admin credit_transactions row.
_SYSTEM_ADMIN_ID = 0


class PaymentService:
    def __init__(
        self,
        gateway: PaymentGateway | None,
        repository: PaymentRepository,
        credits: CreditService,
        *,
        coupons: CouponService | None = None,
        clock=None,
    ):
        self.gateway = gateway
        self.repository = repository
        self.credits = credits
        # Optional so every existing construction of this service keeps
        # working; a checkout that passes no code never touches it.
        self.coupons = coupons
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- founder-initiated ---------------------------------------------------

    def start_checkout(self, founder_id: int, tier: PlanTier,
                       coupon_code: str | None = None) -> CheckoutSession:
        if self.gateway is None:
            raise PaymentsNotConfiguredError()

        plan = PLANS.get(tier)
        if plan is None:
            raise InvalidCheckoutError(f"unknown plan {tier!r}")
        if not plan.is_paid:
            raise InvalidCheckoutError("the free plan needs no checkout")

        # The price is decided HERE, from the catalog, and the founder only
        # ever sends a code -- never an amount. A discount applied at the
        # gateway instead would charge one number while `payments.amount_inr`
        # recorded another, and the admin revenue views read that column.
        list_amount_inr = plan.price_inr
        discount_inr = 0
        coupon = None
        if coupon_code and self.coupons is not None:
            # Priced now so the order is created for the right amount; the
            # binding re-check and the slot claim happen below, against the
            # payment row, because the last slot of a capped code can be taken
            # between this line and that one.
            quote = self.coupons.quote(code=coupon_code, tier=tier, founder_id=founder_id)
            discount_inr = quote.discount_inr

        charge_inr = list_amount_inr - discount_inr
        amount_paise = charge_inr * 100
        receipt = f"founder-{founder_id}-{tier.value}-{int(self._now().timestamp())}"

        try:
            order = self.gateway.create_order(
                amount_paise=amount_paise, currency=_CURRENCY, receipt=receipt,
                notes={"founder_id": str(founder_id), "plan_tier": tier.value},
            )
        except PaymentGatewayError as exc:
            # The one log line that says WHY checkout is failing in an
            # environment: Razorpay's own status and error description
            # (401 = the key id/secret configured here are wrong or
            # mismatched, e.g. a test key with a live secret; 400 = a bad
            # field). The founder gets a 502 with a plain message instead of
            # the generic 500 this used to fall through to.
            logger.error("payments: order creation failed",
                         extra={"founder_id": founder_id, "tier": tier.value,
                                "gateway_status": exc.status_code,
                                "gateway_message": exc.gateway_message,
                                "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        # The payment row and the coupon reservation are one transaction: a
        # claimed slot must never outlive the payment it was claimed for, and a
        # discounted payment must never exist without the row that justifies
        # the discount.
        payment_id = self.repository.create_pending(
            founder_id=founder_id, amount_inr=charge_inr, currency=_CURRENCY,
            gateway="razorpay", gateway_order_id=order.order_id,
            # What this payment buys, recorded where the price was decided.
            # The gateway's notes carry it too, but those come back through
            # the browser and are not authority for a grant.
            plan_tier=tier.value,
            coupon_id=None,
            list_amount_inr=list_amount_inr if discount_inr else None,
            discount_inr=discount_inr or None,
            commit=coupon_code is None or self.coupons is None,
        )

        if coupon_code and self.coupons is not None:
            try:
                coupon, confirmed_discount = self.coupons.reserve(
                    code=coupon_code, tier=tier, founder_id=founder_id,
                    payment_id=payment_id)
            except Exception:
                # The order exists at Razorpay but nothing here is committed,
                # so the founder sees the coupon error and no orphan payment
                # row is left behind. An uncaptured order costs nothing.
                self.repository.db.rollback()
                raise
            self.repository.attach_coupon(payment_id, coupon_id=coupon.coupon_id,
                                          discount_inr=confirmed_discount)
            logger.info("payments: coupon applied to checkout",
                        extra={"founder_id": founder_id, "tier": tier.value,
                               "coupon": coupon.code, "discount_inr": confirmed_discount,
                               "charged_inr": charge_inr})

        return CheckoutSession(
            payment_id=payment_id, order_id=order.order_id, amount_paise=order.amount_paise,
            currency=order.currency, key_id=self.gateway.key_id,
            list_amount_paise=list_amount_inr * 100 if discount_inr else None,
            discount_paise=discount_inr * 100 if discount_inr else None,
            coupon_code=coupon.code if coupon is not None else None,
        )

    def set_billing(self, founder_id: int, payment_id: int, billing_payload: Any) -> None:
        """Attach the personal/business answer and invoice details the
        checkout screen collected.

        Ownership is checked before anything is written, the same way
        `confirm_checkout` checks it: this endpoint is reachable with a
        founder's own token, so a payment id belonging to someone else must
        look exactly like one that does not exist. Beyond that nothing here
        can fail loudly -- `parse_billing` drops whatever does not validate
        rather than raising, because a GSTIN typo must never be able to
        interrupt a checkout that is otherwise fine.
        """
        payment = self.repository.get_by_payment_id(payment_id)
        if payment is None or payment.founder_id != founder_id:
            raise PaymentNotFoundError()

        billing = parse_billing(billing_payload)
        self.repository.set_billing(payment_id, billing)

    def confirm_checkout(self, founder_id: int, *, order_id: str, gateway_payment_id: str,
                         signature: str | None = None) -> WebhookResult:
        """Settle a just-completed checkout now instead of waiting on the webhook.

        The founder's tab calls this the moment Razorpay's handler fires. It
        does not shortcut anything the webhook checks -- it runs the identical
        grant -- it only removes the wait for a delivery that is entirely
        Razorpay's to schedule. The founder therefore stops staring at
        "activating your plan" a round trip after paying rather than however
        long the webhook happens to take.

        Ownership is checked before anything is fetched: this endpoint is
        reachable with a founder's own token, so an order id belonging to
        someone else must look exactly like an order id that does not exist.
        """
        if self.gateway is None:
            raise PaymentsNotConfiguredError()

        payment = self.repository.get_by_gateway_order_id(order_id)
        if payment is None or payment.founder_id != founder_id:
            raise PaymentNotFoundError()

        # The webhook may well have beaten us here -- that is the happy case,
        # not an error, and it costs a Razorpay round trip to discover the
        # hard way.
        if payment.status == "success":
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 payment_id=payment.payment_id, founder_id=payment.founder_id)

        if signature and not self.gateway.verify_checkout_signature(
            order_id=order_id, payment_id=gateway_payment_id, signature=signature
        ):
            logger.warning("payments: checkout callback signature verification failed",
                           extra={"founder_id": founder_id, "gateway_order_id": order_id,
                                  "gateway_payment_id": gateway_payment_id})
            raise InvalidCheckoutCallbackError()

        try:
            entity = self.gateway.fetch_payment(gateway_payment_id)
        except PaymentGatewayError as exc:
            # Not a failure the founder should be shown as "payment failed":
            # they have been charged, and the webhook is still coming. The
            # caller falls back to polling.
            logger.warning("payments: could not confirm payment with the gateway",
                           extra={"founder_id": founder_id, "gateway_payment_id": gateway_payment_id,
                                  "gateway_status": exc.status_code, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        # The entity must be the one this order was created for. Without this,
        # a founder could quote someone else's captured payment id against
        # their own pending order.
        if entity.get("order_id") != order_id:
            logger.error("payments: confirm quoted a payment belonging to another order",
                         extra={"founder_id": founder_id, "gateway_order_id": order_id,
                                "entity_order_id": entity.get("order_id")})
            raise PaymentNotFoundError()

        if entity.get("status") != "captured":
            # Authorised-but-not-captured, or still in flight. Nothing to grant
            # yet and nothing wrong: the webhook will land when it lands.
            logger.info("payments: confirm found the payment not yet captured",
                        extra={"founder_id": founder_id, "gateway_payment_id": gateway_payment_id,
                               "gateway_status": entity.get("status")})
            return WebhookResult(outcome=WebhookOutcome.NOT_CAPTURED,
                                 payment_id=payment.payment_id, founder_id=payment.founder_id)

        return self._grant_for_captured(entity)

    # --- gateway-initiated ---------------------------------------------------

    def handle_webhook(self, *, body: bytes, signature: str) -> WebhookResult:
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        if not self.gateway.verify_webhook_signature(body=body, signature=signature):
            logger.warning("payments: webhook signature verification failed")
            raise InvalidWebhookSignatureError()

        payload = json.loads(body)
        event = payload.get("event")
        entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}

        if event == "payment.captured":
            return self._grant_for_captured(entity)
        if event == "payment.failed":
            return self._handle_failed(entity)

        logger.info("payments: webhook event not handled", extra={"event": event})
        return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT)

    def _grant_for_captured(self, entity: dict[str, Any]) -> WebhookResult:
        """The one grant, shared by the webhook and by confirm_checkout.

        Both callers have established the same fact before reaching here --
        Razorpay says this payment entity is captured -- so neither gets its
        own version of "what a payment buys", and the idempotency check below
        is what makes it safe for both to arrive."""
        gateway_payment_id = entity.get("id")
        gateway_order_id = entity.get("order_id")

        # Idempotency: Razorpay retries webhook deliveries on anything short
        # of a 2xx, and this handler must be safe to run twice for the same
        # payment -- a plan or credit grant must never apply twice.
        if gateway_payment_id and self.repository.get_by_gateway_payment_id(gateway_payment_id):
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED)

        payment = self.repository.get_by_gateway_order_id(gateway_order_id)
        if payment is None:
            # A captured payment for an order this backend never created --
            # never silently grant a plan to nobody in particular.
            logger.error("payments: captured webhook for an unknown order",
                         extra={"gateway_order_id": gateway_order_id,
                                "gateway_payment_id": gateway_payment_id})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        # WHAT THIS PAYMENT BUYS COMES FROM OUR OWN ROW, written when the order
        # was priced -- never from the gateway's notes.
        #
        # It used to be the notes, on the premise (gateway.py) that Razorpay
        # copies order notes onto the payment entity. The browser's Checkout
        # options carry their own `notes` and ours sent `{plan_name: ...}`, so
        # `plan_tier` was not on the entity at all: this branch refused the
        # grant on every payment made through the widget. The founder was
        # charged and given nothing, which is exactly what happened to the
        # founder who paid Rs 999 and stayed on the Rs 199 plan.
        #
        # And notes are browser-supplied, so reading the tier from them meant
        # the amount charged and the plan granted had different authorities:
        # buy the cheapest tier, send `plan_tier: pro`, receive Pro.
        notes = entity.get("notes") or {}
        tier_value = payment.plan_tier
        source = "payment row"
        if not tier_value:
            # Rows created before payments.plan_tier existed. Fall back so an
            # in-flight checkout from the old build still completes, and say so
            # loudly -- this path is temporary and unverifiable.
            tier_value = notes.get("plan_tier")
            source = "gateway notes (legacy payment row)"
        elif notes.get("plan_tier") and notes["plan_tier"] != tier_value:
            # Not fatal -- our row wins and the grant proceeds -- but a
            # mismatch is either a gateway change or someone trying it on.
            logger.error("payments: gateway notes disagree with the recorded plan tier",
                         extra={"payment_id": payment.payment_id,
                                "recorded": tier_value, "notes_tier": notes.get("plan_tier")})

        try:
            tier = PlanTier(tier_value)
            plan = PLANS[tier]
        except (ValueError, KeyError):
            logger.error("payments: captured payment names no recognisable plan tier",
                         extra={"payment_id": payment.payment_id, "source": source,
                                "tier_value": tier_value, "notes": notes})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT,
                                 payment_id=payment.payment_id, founder_id=payment.founder_id)

        now = self._now()
        # A one-time tier buys one diagnosis, not a month of service: it has no
        # cycle to renew and nothing to expire, so it gets no expiry date. The
        # old code stamped every purchase as monthly with a 30-day expiry, which
        # for Basic was simply untrue -- and an expiry nothing enforces today is
        # the sort of field something enforces later.
        one_time = plan.one_time
        expires_at = None if one_time else _one_month_after(now)

        subscription_id = self.repository.create_subscription(
            founder_id=payment.founder_id, plan_type=tier.value, amount_inr=payment.amount_inr,
            billing_cycle="one_time" if one_time else "monthly",
            expires_at=expires_at, gateway="razorpay",
        )
        self.repository.mark_captured(
            payment.payment_id, gateway_payment_id=gateway_payment_id, paid_at=now,
            subscription_id=subscription_id,
        )
        self.repository.grant_plan(payment.founder_id, tier.value)

        # The slot is spent for good. Done after the plan grant, and never in a
        # way that can undo it: a founder who paid and got their plan must not
        # lose it because a bookkeeping update failed.
        if self.coupons is not None:
            try:
                self.coupons.repository.confirm_for_payment(payment.payment_id, at=now)
                self.repository.db.commit()
            except Exception as exc:  # noqa: BLE001 -- the grant above must stand
                logger.error("payments: plan granted but coupon redemption not confirmed",
                             extra={"payment_id": payment.payment_id,
                                    "founder_id": payment.founder_id, "error": str(exc)})

        if plan.monthly_credits:
            try:
                self.credits.adjust(
                    payment.founder_id, admin_id=_SYSTEM_ADMIN_ID, operation=CreditOperation.ADD,
                    amount=plan.monthly_credits,
                    reason=f"{plan.name} plan payment captured ({gateway_payment_id})",
                )
            except Exception as exc:  # noqa: BLE001 -- the plan grant above must still stand
                # The plan itself is already granted and committed -- a credit
                # grant failure here must not roll that back or fail the whole
                # webhook (which would make Razorpay retry a payment that
                # already succeeded). Surfaced loudly instead: this founder is
                # on the right plan with a short credit balance until someone
                # notices and tops it up by hand.
                logger.error("payments: plan granted but credit grant failed",
                            extra={"founder_id": payment.founder_id, "payment_id": payment.payment_id,
                                   "error": str(exc)})

        logger.info("payments: plan granted from a captured payment",
                    extra={"founder_id": payment.founder_id, "payment_id": payment.payment_id,
                          "plan": tier.value})
        return WebhookResult(outcome=WebhookOutcome.CAPTURED, payment_id=payment.payment_id,
                             founder_id=payment.founder_id, plan=tier.value, granted_at=now)

    def _handle_failed(self, entity: dict[str, Any]) -> WebhookResult:
        gateway_order_id = entity.get("order_id")
        payment = self.repository.get_by_gateway_order_id(gateway_order_id)
        if payment is None:
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        reason = entity.get("error_description") or "payment failed"
        self.repository.mark_failed(payment.payment_id, reason=reason)

        # Hand the slot back now rather than waiting out the pending TTL. On a
        # capped code that difference is the next founder getting in.
        if self.coupons is not None:
            try:
                self.coupons.repository.release_for_payment(payment.payment_id)
                self.repository.db.commit()
            except Exception as exc:  # noqa: BLE001 -- recording the failure matters more
                logger.error("payments: could not release coupon slot for a failed payment",
                             extra={"payment_id": payment.payment_id, "error": str(exc)})
        logger.info("payments: payment failed", extra={"payment_id": payment.payment_id,
                                                        "founder_id": payment.founder_id,
                                                        "reason": reason})
        return WebhookResult(outcome=WebhookOutcome.FAILED_RECORDED, payment_id=payment.payment_id,
                             founder_id=payment.founder_id)
