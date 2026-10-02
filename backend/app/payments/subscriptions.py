"""Paid trial + Razorpay autopay.

What the founder buys
---------------------
A TRIAL_DAYS (10) trial of any paid tier for that tier's `trial_price_inr`
(Starter Rs 19, Plus Rs 29, Pro Rs 49). Paying it and setting up autopay are
one step. Unless they cancel, autopay charges on day 11 the plan price less the
trial fee (Pro: Rs 950), then the full price monthly for Plus and Pro. Starter
is charged on day 11 and never again.

How that maps onto Razorpay
---------------------------
One Razorpay *subscription* per trial, on a monthly plan at the tier's full
price (settings.RAZORPAY_PLAN_ID_*):

  - `start_at` = the end of the trial, so the first cycle charge lands on day 11;
  - an upfront ADDON of the trial fee, which Razorpay charges in the same
    transaction that authorises the mandate;
  - a subscription OFFER (settings.RAZORPAY_TRIAL_OFFER_ID_*) worth the trial
    fee, on the first payment only -- which is what makes day 11 Rs 950;
  - `total_count` 1 for Starter, so its mandate charges exactly once.

The lifecycle, and what each step does here
-------------------------------------------
  start_trial                  row 'pending' -- nothing granted, nothing paid
  subscription.authenticated   row 'trial', plan granted, trial credits added
    (or confirm_trial, the founder's tab asking first -- same idempotent step)
  subscription.charged         row 'active', paid period set, monthly credits
  subscription.cancelled       row 'cancelled'; access runs to the period end
  subscription.halted          autopay failed every retry: row 'expired', plan
                               revoked now
  expire_lapsed (sweep)        revokes cancelled plans once their period ends

As in service.py, the browser is never evidence: a grant follows only from a
signed webhook or from asking Razorpay directly, and every grant is idempotent
on Razorpay's payment id (charges) or on the row's status (activation).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.core.config import settings
from app.core.logger import logger
from app.credits.models import CreditOperation
from app.payments.errors import (
    AutopayAlreadyActiveError,
    InvalidCheckoutCallbackError,
    NoAutopayError,
    PaymentGatewayUnavailableError,
    PaymentNotFoundError,
    PaymentsNotConfiguredError,
    TrialAlreadyUsedError,
    TrialUnavailableError,
)
from app.payments.gateway import PaymentGateway, PaymentGatewayError
from app.payments.models import SubscriptionRecord, TrialCheckout, WebhookOutcome, WebhookResult
from app.payments.repository import PaymentRepository
from app.plans.catalog import PLANS, TRIAL_DAYS, Plan, PlanTier

_SYSTEM_ADMIN_ID = 0

#: Razorpay needs a cycle count. Ten years of months is "until cancelled".
_RECURRING_TOTAL_COUNT = 120

#: How long the founder has to complete the authorisation before Razorpay
#: expires the unauthorised subscription.
_AUTHORISE_WITHIN = timedelta(days=1)

#: A captured payment made this long before the trial ends cannot be a cycle
#: charge -- the first one is scheduled for the trial's end -- so it is the
#: trial fee. Generous on purpose: Razorpay charges near `start_at`, not before.
_TRIAL_FEE_MARGIN = timedelta(hours=12)


def _from_epoch(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc) if value else None
    except (TypeError, ValueError, OverflowError):
        return None


def _rupees(entity: dict[str, Any]) -> int:
    return int(entity.get("amount") or 0) // 100


class SubscriptionService:
    def __init__(
        self,
        gateway: PaymentGateway | None,
        repository: PaymentRepository,
        credits,
        *,
        trial_ids: Callable[[str], tuple[str, str] | None] | None = None,
        clock=None,
    ):
        self.gateway = gateway
        self.repository = repository
        self.credits = credits
        self._trial_ids = trial_ids or settings.razorpay_trial_ids
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- founder-initiated ---------------------------------------------------

    def trial_available(self, tier: PlanTier) -> bool:
        plan = PLANS.get(tier)
        return bool(plan and plan.offers_trial and self._trial_ids(tier.value))

    def start_trial(self, founder_id: int, tier: PlanTier) -> TrialCheckout:
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        plan = PLANS.get(tier)
        if plan is None or not plan.offers_trial:
            raise TrialUnavailableError(plan.name if plan else str(tier))
        ids = self._trial_ids(tier.value)
        if ids is None:
            # A missing offer id would mean charging the trial fee ON TOP of the
            # first month. Refuse rather than overcharge.
            logger.error("payments: trial requested but Razorpay plan/offer ids are not set",
                         extra={"tier": tier.value})
            raise TrialUnavailableError(plan.name)
        plan_id, offer_id = ids

        if self.repository.has_used_trial(founder_id):
            raise TrialAlreadyUsedError()
        now = self._now()
        current = self.repository.get_current_autopay(founder_id)
        if current is not None and current.status in ("trial", "active") and (
                current.access_until is None or current.access_until > now):
            raise AutopayAlreadyActiveError()

        trial_ends_at = now + timedelta(days=TRIAL_DAYS)
        try:
            created = self.gateway.create_subscription(
                plan_id=plan_id,
                total_count=1 if plan.one_time else _RECURRING_TOTAL_COUNT,
                start_at=int(trial_ends_at.timestamp()),
                offer_id=offer_id,
                upfront_amount_paise=plan.trial_price_inr * 100,
                upfront_label=f"{plan.name} {TRIAL_DAYS}-day trial",
                expire_by=int((now + _AUTHORISE_WITHIN).timestamp()),
                notes={"founder_id": str(founder_id), "plan_tier": tier.value,
                       "kind": "trial"},
            )
        except PaymentGatewayError as exc:
            logger.error("payments: trial subscription creation failed",
                         extra={"founder_id": founder_id, "tier": tier.value,
                                "gateway_status": exc.status_code,
                                "gateway_message": exc.gateway_message, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        self.repository.create_pending_subscription(
            founder_id=founder_id, plan_type=tier.value, amount_inr=plan.price_inr,
            billing_cycle="one_time" if plan.one_time else "monthly",
            trial_ends_at=trial_ends_at, gateway_subscription_id=created.subscription_id,
        )
        return TrialCheckout(
            subscription_id=created.subscription_id, key_id=self.gateway.key_id,
            plan_name=plan.name, trial_days=TRIAL_DAYS,
            trial_amount_paise=plan.trial_price_inr * 100,
            plan_amount_paise=plan.price_inr * 100,
            first_charge_paise=plan.first_charge_inr * 100,
            trial_ends_at=trial_ends_at, recurring=not plan.one_time,
        )

    def confirm_trial(self, founder_id: int, *, gateway_subscription_id: str,
                      gateway_payment_id: str, signature: str | None = None) -> WebhookResult:
        """The founder's tab says Checkout.js finished; ask Razorpay whether the
        mandate really is authorised, and start the trial now instead of on the
        webhook's schedule. Same ownership-first shape as confirm_checkout."""
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        row = self.repository.get_subscription_by_gateway_id(gateway_subscription_id)
        if row is None or row.founder_id != founder_id:
            raise PaymentNotFoundError()

        verified = False
        if signature:
            if not self.gateway.verify_subscription_checkout_signature(
                    subscription_id=gateway_subscription_id, payment_id=gateway_payment_id,
                    signature=signature):
                logger.warning("payments: trial callback signature verification failed",
                               extra={"founder_id": founder_id,
                                      "gateway_subscription_id": gateway_subscription_id})
                raise InvalidCheckoutCallbackError()
            verified = True

        try:
            entity = self.gateway.fetch_subscription(gateway_subscription_id)
        except PaymentGatewayError as exc:
            logger.warning("payments: could not confirm trial with the gateway",
                           extra={"founder_id": founder_id, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        if entity.get("status") not in ("authenticated", "active"):
            return WebhookResult(outcome=WebhookOutcome.NOT_CAPTURED, founder_id=founder_id)

        # Only a signed callback ties this payment id to this subscription; an
        # unsigned one still starts the trial (Razorpay said authenticated) but
        # leaves recording the fee to the webhook.
        payment = None
        if verified and gateway_payment_id:
            try:
                payment = self.gateway.fetch_payment(gateway_payment_id)
            except PaymentGatewayError:
                payment = None
        return self._activate_trial(row, payment)

    def cancel(self, founder_id: int) -> dict | None:
        """Stop autopay. In the trial this cancels at once, so the day-11 charge
        never happens; once paid it cancels at the cycle's end, so nothing
        already paid for is taken away. Either way the plan stays until then."""
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        row = self.repository.get_current_autopay(founder_id)
        if row is None or row.status not in ("trial", "active") or (
                row.status == "active" and row.billing_cycle == "one_time"):
            raise NoAutopayError()

        at_cycle_end = row.status == "active"
        try:
            self.gateway.cancel_subscription(row.gateway_subscription_id,
                                             at_cycle_end=at_cycle_end)
        except PaymentGatewayError as exc:
            logger.error("payments: autopay cancel failed",
                         extra={"founder_id": founder_id, "gateway_status": exc.status_code,
                                "gateway_message": exc.gateway_message, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        self.repository.update_subscription(
            row.subscription_id, status="cancelled", cancelled_at=self._now(),
            cancellation_reason="cancelled by founder")
        logger.info("payments: autopay cancelled by founder",
                    extra={"founder_id": founder_id, "plan": row.plan_type,
                           "during_trial": not at_cycle_end})
        return self.status(founder_id)

    def status(self, founder_id: int) -> dict | None:
        """What the billing page shows: where the trial/autopay stands, and the
        next charge -- amount and date -- if there is one."""
        row = self.repository.get_current_autopay(founder_id)
        if row is None:
            return None
        plan = self._plan(row)
        next_charge_at, next_charge_inr = None, None
        if plan is not None and row.status == "trial":
            next_charge_at, next_charge_inr = row.trial_ends_at, plan.first_charge_inr
        elif plan is not None and row.status == "active" and row.billing_cycle != "one_time":
            next_charge_at, next_charge_inr = row.expires_at, plan.price_inr
        return {
            "plan": row.plan_type,
            "plan_name": plan.name if plan else row.plan_type,
            "status": row.status,
            "recurring": row.billing_cycle != "one_time",
            "trial_ends_at": row.trial_ends_at,
            "access_until": row.access_until,
            "next_charge_at": next_charge_at,
            "next_charge_inr": next_charge_inr,
            "cancelled_at": row.cancelled_at,
            "can_cancel": row.status in ("trial", "active") and not (
                row.status == "active" and row.billing_cycle == "one_time"),
        }

    # --- gateway-initiated ---------------------------------------------------

    def handle_event(self, event: str, payload: dict[str, Any]) -> WebhookResult:
        inner = payload.get("payload") or {}
        sub = (inner.get("subscription") or {}).get("entity") or {}
        payment = (inner.get("payment") or {}).get("entity") or None

        row = self.repository.get_subscription_by_gateway_id(sub.get("id") or "")
        if row is None:
            logger.error("payments: subscription event for an unknown subscription",
                         extra={"event": event, "gateway_subscription_id": sub.get("id")})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        if event in ("subscription.authenticated", "subscription.activated"):
            return self._activate_trial(row, payment)
        if event == "subscription.charged":
            return self._on_captured(row, payment, sub)
        if event == "subscription.cancelled":
            return self._on_cancelled(row)
        if event == "subscription.halted":
            return self._end(row, reason="autopay charge failed every retry")
        if event == "subscription.completed":
            if row.billing_cycle == "one_time":
                # Starter's single charge is done; its month stands.
                return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT,
                                     founder_id=row.founder_id)
            return self._end(row, reason="subscription completed")
        if event == "subscription.pending":
            logger.warning("payments: autopay charge failed; Razorpay is retrying",
                           extra={"founder_id": row.founder_id, "plan": row.plan_type})
        return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT, founder_id=row.founder_id)

    def handle_invoice_payment(self, entity: dict[str, Any]) -> WebhookResult | None:
        """A `payment.captured` for an order this backend never created, carrying
        an `invoice_id`: an autopay payment. The invoice names the subscription.
        None when it is not one of ours, so the caller reports it as before."""
        invoice_id = entity.get("invoice_id")
        if not invoice_id or self.gateway is None:
            return None
        try:
            invoice = self.gateway.fetch_invoice(invoice_id)
        except PaymentGatewayError as exc:
            logger.warning("payments: could not read the invoice behind a captured payment",
                           extra={"invoice_id": invoice_id, "error": str(exc)})
            return None
        row = self.repository.get_subscription_by_gateway_id(invoice.get("subscription_id") or "")
        if row is None:
            return None
        return self._on_captured(row, entity, None)

    def expire_lapsed(self) -> dict:
        """The sweep: revoke plans whose cancelled or failed autopay period has
        run out. Idempotent -- a founder already moved off the plan is not
        selected again."""
        now = self._now()
        lapsed = self.repository.find_lapsed_autopay(now)
        revoked = sum(1 for row in lapsed if self._revoke(row, now))
        return {"checked": len(lapsed), "revoked": revoked}

    # --- internals -----------------------------------------------------------

    def _plan(self, row: SubscriptionRecord) -> Plan | None:
        try:
            return PLANS[PlanTier(row.plan_type)]
        except (ValueError, KeyError):
            return None

    def _activate_trial(self, row: SubscriptionRecord,
                        payment: dict[str, Any] | None) -> WebhookResult:
        """Mandate authorised and trial fee paid: start the trial. Idempotent on
        the row's status, so the webhook and the founder's confirm can both
        arrive."""
        if payment and payment.get("status") == "captured":
            self._record_payment(row, payment)
        if row.status != "pending":
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=row.founder_id, plan=row.plan_type)

        plan = self._plan(row)
        self.repository.update_subscription(row.subscription_id, status="trial")
        self.repository.grant_plan(row.founder_id, row.plan_type)
        if plan is not None and plan.trial_credits:
            self._add_credits(row, plan.trial_credits,
                              f"{plan.name} {TRIAL_DAYS}-day trial started")
        logger.info("payments: trial started", extra={"founder_id": row.founder_id,
                                                     "plan": row.plan_type})
        return WebhookResult(outcome=WebhookOutcome.TRIAL_STARTED, founder_id=row.founder_id,
                             plan=row.plan_type, granted_at=self._now())

    def _on_captured(self, row: SubscriptionRecord, payment: dict[str, Any] | None,
                     sub: dict[str, Any] | None) -> WebhookResult:
        """One captured payment on a subscription: the trial fee, or a cycle
        charge. Told apart by time -- no cycle charge can precede the trial's end."""
        if not payment or not payment.get("id"):
            return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT, founder_id=row.founder_id)
        if self.repository.get_by_gateway_payment_id(payment["id"]):
            # Already handled through the other path (webhook vs invoice lookup,
            # or a Razorpay retry). Granting again would double the credits.
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=row.founder_id)

        paid_at = _from_epoch(payment.get("created_at")) or self._now()
        if row.status == "pending" or (
                row.trial_ends_at is not None and paid_at < row.trial_ends_at - _TRIAL_FEE_MARGIN):
            return self._activate_trial(row, payment)
        return self._renew(row, payment, sub)

    def _renew(self, row: SubscriptionRecord, payment: dict[str, Any],
               sub: dict[str, Any] | None) -> WebhookResult:
        plan = self._plan(row)
        now = self._now()
        self._record_payment(row, payment)

        if row.billing_cycle == "one_time":
            # Starter: the single day-11 charge buys its month outright.
            self.repository.update_subscription(row.subscription_id, status="active",
                                                clear_expiry=True)
        else:
            period_end = _from_epoch((sub or {}).get("current_end"))
            if period_end is None or period_end <= now:
                from app.payments.service import _one_month_after
                start = row.access_until if row.access_until and row.access_until > now else now
                period_end = _one_month_after(start)
            # A founder who cancelled for the cycle's end keeps 'cancelled'.
            self.repository.update_subscription(
                row.subscription_id,
                status=None if row.status == "cancelled" else "active",
                expires_at=period_end)

        self.repository.grant_plan(row.founder_id, row.plan_type)
        if plan is not None and plan.monthly_credits:
            self._add_credits(row, plan.monthly_credits,
                              f"{plan.name} autopay charge captured ({payment.get('id')})")
        logger.info("payments: autopay charge captured",
                    extra={"founder_id": row.founder_id, "plan": row.plan_type,
                           "amount_inr": _rupees(payment)})
        return WebhookResult(outcome=WebhookOutcome.RENEWED, founder_id=row.founder_id,
                             plan=row.plan_type, granted_at=now)

    def _on_cancelled(self, row: SubscriptionRecord) -> WebhookResult:
        now = self._now()
        if row.status != "cancelled":
            self.repository.update_subscription(
                row.subscription_id, status="cancelled", cancelled_at=now,
                cancellation_reason="cancelled at Razorpay")
        if row.access_until is not None and row.access_until <= now:
            self._revoke(row, now)
        return WebhookResult(outcome=WebhookOutcome.CANCELLED, founder_id=row.founder_id)

    def _end(self, row: SubscriptionRecord, *, reason: str) -> WebhookResult:
        now = self._now()
        self.repository.update_subscription(row.subscription_id, status="expired",
                                            expires_at=now, cancellation_reason=reason)
        self._revoke(row, now)
        logger.warning("payments: autopay ended, plan revoked",
                       extra={"founder_id": row.founder_id, "plan": row.plan_type,
                              "reason": reason})
        return WebhookResult(outcome=WebhookOutcome.EXPIRED, founder_id=row.founder_id)

    def _revoke(self, row: SubscriptionRecord, now: datetime) -> bool:
        if self.repository.has_other_live_plan(
                row.founder_id, excluding_subscription_id=row.subscription_id, now=now):
            return False
        return self.repository.revoke_plan(row.founder_id, row.plan_type)

    def _record_payment(self, row: SubscriptionRecord, payment: dict[str, Any]) -> None:
        if self.repository.get_by_gateway_payment_id(payment["id"]):
            return
        self.repository.record_subscription_payment(
            founder_id=row.founder_id, subscription_id=row.subscription_id,
            plan_tier=row.plan_type, amount_inr=_rupees(payment),
            gateway_payment_id=payment["id"], gateway_order_id=payment.get("order_id"),
            paid_at=_from_epoch(payment.get("created_at")) or self._now())

    def _add_credits(self, row: SubscriptionRecord, amount: int, reason: str) -> None:
        try:
            self.credits.adjust(row.founder_id, admin_id=_SYSTEM_ADMIN_ID,
                                operation=CreditOperation.ADD, amount=amount, reason=reason)
        except Exception as exc:  # noqa: BLE001 -- the plan grant must still stand
            logger.error("payments: plan granted but credit grant failed",
                         extra={"founder_id": row.founder_id, "amount": amount,
                                "error": str(exc)})
