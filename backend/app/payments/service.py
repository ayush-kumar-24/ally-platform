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
from app.credits.models import CreditOperation
from app.credits.service import CreditService
from app.payments.errors import (
    InvalidCheckoutError,
    InvalidWebhookSignatureError,
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
        clock=None,
    ):
        self.gateway = gateway
        self.repository = repository
        self.credits = credits
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- founder-initiated ---------------------------------------------------

    def start_checkout(self, founder_id: int, tier: PlanTier) -> CheckoutSession:
        if self.gateway is None:
            raise PaymentsNotConfiguredError()

        plan = PLANS.get(tier)
        if plan is None:
            raise InvalidCheckoutError(f"unknown plan {tier!r}")
        if not plan.is_paid:
            raise InvalidCheckoutError("the free plan needs no checkout")

        amount_paise = plan.price_inr * 100
        receipt = f"founder-{founder_id}-{tier.value}-{int(self._now().timestamp())}"

        try:
            order = self.gateway.create_order(
                amount_paise=amount_paise, currency=_CURRENCY, receipt=receipt,
                notes={"founder_id": str(founder_id), "plan_tier": tier.value},
            )
        except PaymentGatewayError:
            logger.error("payments: order creation failed",
                         extra={"founder_id": founder_id, "tier": tier.value})
            raise

        payment_id = self.repository.create_pending(
            founder_id=founder_id, amount_inr=plan.price_inr, currency=_CURRENCY,
            gateway="razorpay", gateway_order_id=order.order_id,
        )
        return CheckoutSession(
            payment_id=payment_id, order_id=order.order_id, amount_paise=order.amount_paise,
            currency=order.currency, key_id=self.gateway.key_id,
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
        expires_at = now + timedelta(days=_BILLING_CYCLE_DAYS)

        subscription_id = self.repository.create_subscription(
            founder_id=payment.founder_id, plan_type=tier.value, amount_inr=payment.amount_inr,
            billing_cycle="monthly", expires_at=expires_at, gateway="razorpay",
        )
        self.repository.mark_captured(
            payment.payment_id, gateway_payment_id=gateway_payment_id, paid_at=now,
            subscription_id=subscription_id,
        )
        self.repository.grant_plan(payment.founder_id, tier.value)

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
        logger.info("payments: payment failed", extra={"payment_id": payment.payment_id,
                                                        "founder_id": payment.founder_id,
                                                        "reason": reason})
        return WebhookResult(outcome=WebhookOutcome.FAILED_RECORDED, payment_id=payment.payment_id,
                             founder_id=payment.founder_id)
