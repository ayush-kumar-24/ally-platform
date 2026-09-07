"""PaymentService -- start_checkout (founder-initiated) and handle_webhook
(gateway-initiated, the only path that actually grants anything).

Why the plan is granted from the webhook and not from the frontend's
post-checkout redirect: the redirect is a browser navigation the founder's
own client controls -- closing the tab loses it, and nothing stops a request
forged straight at a "confirm payment" endpoint from claiming success it
never earned. The webhook is server-to-server and signed with a secret only
Razorpay and this backend hold; it is the only signal this service trusts
enough to hand out a plan.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logger import logger
from app.coupons.service import CouponService
from app.credits.models import CreditOperation
from app.credits.service import CreditService
from app.payments.errors import (
    InvalidCheckoutError,
    InvalidWebhookSignatureError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
)
from app.payments.gateway import PaymentGateway, PaymentGatewayError
from app.payments.models import CheckoutSession, WebhookOutcome, WebhookResult
from app.payments.repository import PaymentRepository
from app.plans.catalog import PLANS, PlanTier

_CURRENCY = "INR"
_BILLING_CYCLE_DAYS = 30

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

    # --- gateway-initiated: the only path that grants anything --------------

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
            return self._handle_captured(entity)
        if event == "payment.failed":
            return self._handle_failed(entity)

        logger.info("payments: webhook event not handled", extra={"event": event})
        return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT)

    def _handle_captured(self, entity: dict[str, Any]) -> WebhookResult:
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

        notes = entity.get("notes") or {}
        tier_value = notes.get("plan_tier")
        try:
            tier = PlanTier(tier_value)
            plan = PLANS[tier]
        except (ValueError, KeyError):
            logger.error("payments: captured payment carries no recognisable plan_tier note",
                         extra={"payment_id": payment.payment_id, "notes": notes})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT,
                                 payment_id=payment.payment_id, founder_id=payment.founder_id)

        now = self._now()
        # A one-time tier buys one diagnosis, not a month of service: it has no
        # cycle to renew and nothing to expire, so it gets no expiry date. The
        # old code stamped every purchase as monthly with a 30-day expiry, which
        # for Basic was simply untrue -- and an expiry nothing enforces today is
        # the sort of field something enforces later.
        one_time = plan.one_time
        expires_at = None if one_time else now + timedelta(days=_BILLING_CYCLE_DAYS)

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
