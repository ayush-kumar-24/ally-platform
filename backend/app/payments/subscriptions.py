"""SubscriptionService -- the recurring half of billing: Plus (Rs 499) and
Pro (Rs 999).

WHY THIS MODULE EXISTS. Before it, every paid tier went through a one-time
Razorpay ORDER. That works exactly once. There was no mandate, so no second
month was ever charged; the subscriptions row carried `expires_at = now + 30
days` and nothing renewed it, enforced it, or told the founder about it. A
founder paid Rs 499 and kept Plus indefinitely.

THE ONE RULE. Access is granted by money arriving, and by nothing else. A
subscription that exists grants nothing. A mandate the founder has
authorised grants nothing. `subscription.charged` -- Razorpay telling us,
server-to-server under the webhook secret, that it took the money -- is the
only event in this module that moves a founder onto a paid plan, and
`_grant_cycle` is the only method that does it. Everything else here mirrors
state so the billing page can be honest.

THE ACCESS CLOCK. `subscriptions.access_until` is what paid features run on,
and it is set to `current_period_end + SUBSCRIPTION_GRACE_DAYS` on every
successful charge. That single line is the whole failed-payment policy:

  - Renewal succeeds on time -> the clock jumps forward a month anyway.
  - Renewal fails -> the founder keeps working for the grace window while
    Razorpay runs its own retries (guide step 12 is explicit that the retry
    schedule is Razorpay's and must not be reinvented here).
  - Razorpay gives up and halts the subscription -> `_on_halted` truncates
    the clock to now, and the sweep restricts access on its next run.

No timer, no scheduled downgrade job racing the retries, and no state where
the founder is charged but locked out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.credits.models import CreditOperation
from app.payments.errors import (
    InvalidCheckoutError,
    NoActiveSubscriptionError,
    PaymentsNotConfiguredError,
    PaymentGatewayUnavailableError,
    SubscriptionAlreadyActiveError,
    SubscriptionPlanNotConfiguredError,
)
from app.payments.gateway import PaymentGatewayError
from app.payments.models import WebhookOutcome, WebhookResult
from app.payments.subscription_repository import (
    SubscriptionRecord,
    SubscriptionRepository,
    epoch_to_dt,
)
from app.plans.catalog import PLANS, PlanTier

_CURRENCY = "INR"

#: Same sentinel app/plans/service.py and PaymentService already use for a
#: credit_transactions row that no admin caused.
_SYSTEM_ADMIN_ID = 0

#: Events this module owns. Anything else the webhook route hands us is
#: reported as ignored rather than silently swallowed.
SUBSCRIPTION_EVENTS = (
    "subscription.authenticated",
    "subscription.activated",
    "subscription.charged",
    "subscription.pending",
    "subscription.halted",
    "subscription.cancelled",
    "subscription.completed",
    "subscription.updated",
    "invoice.paid",
)


@dataclass(frozen=True)
class SubscriptionCheckoutSession:
    """What the browser needs to open Razorpay Checkout in subscription mode.

    Note there is no `amount`: a subscription checkout is authorising a
    mandate against a PLAN, and the plan's amount is fixed at Razorpay. The
    price shown to the founder comes from our catalog (`amount_inr` below) and
    is display-only -- unlike the one-time path there is no order whose amount
    the browser could contradict, because the browser never names one.
    """

    subscription_id: int
    gateway_subscription_id: str
    razorpay_plan_id: str
    key_id: str
    tier: str
    plan_name: str
    amount_inr: int
    currency: str = _CURRENCY
    short_url: str | None = None


@dataclass(frozen=True)
class CancellationResult:
    subscription_id: int
    status: str
    cancel_at_period_end: bool
    #: When paid features actually stop. The confirmation screen must show
    #: this before the founder confirms, not after (guide step 13).
    access_until: datetime | None


class SubscriptionService:
    def __init__(self, gateway, repository: SubscriptionRepository, payments,
                 credits, *, clock=None):
        self.gateway = gateway
        self.repository = repository
        #: PaymentRepository -- reused rather than reimplemented so a recurring
        #: charge grants a plan through the same `grant_plan` an admin and the
        #: one-time path both write.
        self.payments = payments
        self.credits = credits
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- founder-initiated ---------------------------------------------------

    def start_subscription(self, founder_id: int, tier: PlanTier,
                           ) -> SubscriptionCheckoutSession:
        """Create the mandate the founder is about to authorise.

        Nothing is granted here and nothing is charged here. The row this
        writes exists so the webhook -- which can arrive before the founder's
        browser gets back to us -- has something to attach to.
        """
        if self.gateway is None:
            raise PaymentsNotConfiguredError()

        plan = PLANS.get(tier)
        if plan is None:
            raise InvalidCheckoutError(f"unknown plan {tier!r}")
        if not plan.is_paid:
            raise InvalidCheckoutError("the free plan needs no checkout")
        if plan.one_time:
            # Starter. Creating a monthly mandate for it would charge a founder
            # every month for a single diagnosis they already have -- guide
            # step 3 says this in as many words, and it is worth a hard refusal
            # rather than a comment.
            raise InvalidCheckoutError(
                f"{plan.name} is a one-time purchase -- use the checkout order flow")

        existing = self.repository.live_for_founder(founder_id)
        if existing is not None:
            # Refused, not silently stacked. Two live mandates means two
            # monthly charges, and a founder who clicked Subscribe twice would
            # discover that a month later on their card statement.
            raise SubscriptionAlreadyActiveError(
                plan_name=PLANS[PlanTier(existing.plan_type)].name
                if existing.plan_type in {t.value for t in PlanTier} else existing.plan_type,
                access_until=existing.access_until,
            )

        mode = settings.razorpay_mode
        razorpay_plan_id = self.repository.active_plan_id(tier.value, mode)
        if not razorpay_plan_id:
            logger.error("payments: no razorpay plan registered for this tier",
                         extra={"tier": tier.value, "mode": mode})
            raise SubscriptionPlanNotConfiguredError(plan_name=plan.name)

        try:
            created = self.gateway.create_subscription(
                plan_id=razorpay_plan_id,
                total_count=settings.RAZORPAY_SUBSCRIPTION_TOTAL_COUNT,
                notes={"founder_id": str(founder_id), "plan_tier": tier.value},
            )
        except PaymentGatewayError as exc:
            logger.error("payments: subscription creation failed",
                         extra={"founder_id": founder_id, "tier": tier.value,
                                "razorpay_plan_id": razorpay_plan_id,
                                "gateway_status": exc.status_code,
                                "gateway_message": exc.gateway_message, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        subscription_id = self.repository.create_pending(
            founder_id=founder_id, plan_type=tier.value, amount_inr=plan.price_inr,
            gateway_subscription_id=created.subscription_id,
            razorpay_plan_id=created.plan_id or razorpay_plan_id,
            # Razorpay's own word for it, not one we invent. It is 'created'
            # until the founder authorises the mandate.
            status=created.status or "created",
        )
        logger.info("payments: subscription created, awaiting authorisation",
                    extra={"founder_id": founder_id, "tier": tier.value,
                           "gateway_subscription_id": created.subscription_id})

        return SubscriptionCheckoutSession(
            subscription_id=subscription_id,
            gateway_subscription_id=created.subscription_id,
            razorpay_plan_id=created.plan_id or razorpay_plan_id,
            key_id=self.gateway.key_id, tier=tier.value, plan_name=plan.name,
            amount_inr=plan.price_inr, short_url=created.short_url,
        )

    def cancel(self, founder_id: int, *, at_period_end: bool = True,
               reason: str | None = None) -> CancellationResult:
        """Stop the mandate, keeping the time already paid for.

        `at_period_end=True` is the default and should stay it: the founder has
        paid for this month, and revoking it the instant they click Cancel is
        keeping money for a service withdrawn. Razorpay is told the same thing,
        so neither side is charging again either way.

        The cancellation is recorded from the entity Razorpay hands back, not
        from what we asked for -- if Razorpay cancelled immediately when we
        asked for cycle-end, the founder's access date must reflect what
        actually happened.
        """
        if self.gateway is None:
            raise PaymentsNotConfiguredError()

        subscription = self.repository.live_for_founder(founder_id)
        if subscription is None or not subscription.gateway_subscription_id:
            raise NoActiveSubscriptionError()

        try:
            entity = self.gateway.cancel_subscription(
                subscription.gateway_subscription_id, at_cycle_end=at_period_end)
        except PaymentGatewayError as exc:
            logger.error("payments: subscription cancellation failed at the gateway",
                         extra={"founder_id": founder_id,
                                "gateway_subscription_id": subscription.gateway_subscription_id,
                                "gateway_status": exc.status_code, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        now = self._now()
        status = str(entity.get("status") or ("active" if at_period_end else "cancelled"))
        # Razorpay reports it back; trust that over the flag we sent.
        scheduled = bool(entity.get("cancel_at_cycle_end")) or (
            at_period_end and status != "cancelled")
        period_end = epoch_to_dt(entity.get("current_end")) or subscription.current_period_end
        access_until = period_end if scheduled else now

        self.repository.sync_from_entity(
            subscription.subscription_id, status=status,
            current_period_end=period_end,
            cancelled_at=now, cancel_at_period_end=scheduled,
            ended_at=None if scheduled else now, commit=False)
        # Written unconditionally: an immediate cancellation SHORTENS access,
        # which sync_from_entity's COALESCE contract cannot express.
        self.repository.set_access_until(subscription.subscription_id, access_until)

        if reason:
            self.repository.db.execute(
                _cancellation_reason_sql(), {"reason": reason[:500],
                                             "sid": subscription.subscription_id})
            self.repository.db.commit()

        logger.info("payments: subscription cancelled",
                    extra={"founder_id": founder_id,
                           "gateway_subscription_id": subscription.gateway_subscription_id,
                           "at_period_end": scheduled,
                           "access_until": access_until.isoformat() if access_until else None})
        return CancellationResult(subscription_id=subscription.subscription_id, status=status,
                                  cancel_at_period_end=scheduled, access_until=access_until)

    def current(self, founder_id: int) -> SubscriptionRecord | None:
        """The subscription the billing page shows.

        Falls back to the most recent row of any status so a founder who
        cancelled still sees "cancelled, access until the 3rd" rather than an
        empty page that looks like their payment was lost.
        """
        return (self.repository.live_for_founder(founder_id)
                or self.repository.latest_for_founder(founder_id))

    # --- gateway-initiated ---------------------------------------------------

    def handle_event(self, event: str, payload: dict[str, Any]) -> WebhookResult:
        """Dispatch one already-signature-verified subscription event.

        Called only from PaymentService.handle_webhook, which owns the
        signature check -- there is one verification in the codebase and this
        module is downstream of it, never a second entry point that could be
        reached without it.
        """
        entity = _entity(payload, "subscription")
        if event == "subscription.charged":
            return self._grant_cycle(entity, _entity(payload, "payment"))
        if event == "invoice.paid":
            return self._record_invoice(payload)
        if event in ("subscription.authenticated", "subscription.activated",
                     "subscription.updated"):
            return self._mirror(entity, event)
        if event == "subscription.pending":
            return self._on_pending(entity)
        if event == "subscription.halted":
            return self._on_halted(entity)
        if event in ("subscription.cancelled", "subscription.completed"):
            return self._on_ended(entity, event)

        logger.info("payments: subscription webhook event not handled", extra={"event": event})
        return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT)

    # --- the one grant ------------------------------------------------------

    def _grant_cycle(self, entity: dict, payment_entity: dict) -> WebhookResult:
        """A cycle was charged: record the money, extend access, grant the plan.

        THE ONLY PLACE IN THIS MODULE THAT TOUCHES A FOUNDER'S PLAN. Idempotent
        on the Razorpay payment id via the unique index -- a redelivered event
        inserts nothing, gets None back, and returns without granting or
        crediting twice.
        """
        subscription = self._resolve(entity)
        if subscription is None:
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        gateway_payment_id = str(payment_entity.get("id") or "")
        if not gateway_payment_id:
            # `subscription.charged` without a payment entity is not something
            # to guess at: it would mean granting a month on the strength of an
            # event that names no money.
            logger.error("payments: subscription.charged carried no payment entity",
                         extra={"subscription_id": subscription.subscription_id})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT,
                                 founder_id=subscription.founder_id)

        try:
            tier = PlanTier(subscription.plan_type)
            plan = PLANS[tier]
        except (ValueError, KeyError):
            # The tier comes from OUR row, written when the subscription was
            # created -- never from the event's notes, for the same reason the
            # one-time path stopped reading them (migration d7f4c2e91a63).
            logger.error("payments: subscription names no recognisable plan tier",
                         extra={"subscription_id": subscription.subscription_id,
                                "plan_type": subscription.plan_type})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT,
                                 founder_id=subscription.founder_id)

        now = self._now()
        amount_inr = _paise_to_inr(payment_entity.get("amount"), fallback=plan.price_inr)
        payment_id = self.repository.record_subscription_payment(
            founder_id=subscription.founder_id, subscription_id=subscription.subscription_id,
            amount_inr=amount_inr, currency=str(payment_entity.get("currency") or _CURRENCY),
            gateway_payment_id=gateway_payment_id,
            gateway_order_id=payment_entity.get("order_id"),
            gateway_subscription_id=subscription.gateway_subscription_id or "",
            gateway_invoice_id=payment_entity.get("invoice_id"),
            plan_tier=tier.value, paid_at=now, commit=False)

        if payment_id is None:
            # The unique index refused it: we have already processed this exact
            # charge. Roll back the no-op insert attempt and say so.
            self.repository.db.rollback()
            logger.info("payments: subscription charge already recorded",
                        extra={"gateway_payment_id": gateway_payment_id,
                               "founder_id": subscription.founder_id})
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=subscription.founder_id)

        period_end = epoch_to_dt(entity.get("current_end"))
        # THE ACCESS CLOCK -- see the module docstring. Grace is added here, at
        # the moment of a successful charge, so a later failure needs no
        # separate policy: the founder simply still has time on the clock while
        # Razorpay retries.
        access_until = ((period_end + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS))
                        if period_end else None)

        self.repository.sync_from_entity(
            subscription.subscription_id,
            status="active",
            paid_count=_int_or_none(entity.get("paid_count")),
            current_period_start=epoch_to_dt(entity.get("current_start")),
            current_period_end=period_end,
            next_charge_at=epoch_to_dt(entity.get("charge_at")),
            activated_at=subscription.activated_at or now,
            commit=False)
        if access_until is not None:
            self.repository.set_access_until(subscription.subscription_id, access_until,
                                             commit=False)
        self.repository.db.commit()

        self.payments.grant_plan(subscription.founder_id, tier.value)

        if plan.monthly_credits:
            try:
                self.credits.adjust(
                    subscription.founder_id, admin_id=_SYSTEM_ADMIN_ID,
                    operation=CreditOperation.ADD, amount=plan.monthly_credits,
                    reason=f"{plan.name} subscription charged ({gateway_payment_id})",
                )
            except Exception as exc:  # noqa: BLE001 -- the plan grant above must stand
                # Same call the one-time path makes: the plan is already
                # granted and committed, and failing the webhook here would
                # make Razorpay retry a charge that succeeded.
                logger.error("payments: subscription plan granted but credit grant failed",
                             extra={"founder_id": subscription.founder_id,
                                    "subscription_id": subscription.subscription_id,
                                    "error": str(exc)})

        logger.info("payments: subscription cycle charged and access extended",
                    extra={"founder_id": subscription.founder_id, "plan": tier.value,
                           "paid_count": entity.get("paid_count"),
                           "access_until": access_until.isoformat() if access_until else None})
        return WebhookResult(outcome=WebhookOutcome.CAPTURED, payment_id=payment_id,
                             founder_id=subscription.founder_id, plan=tier.value,
                             granted_at=now)

    # --- state mirrors (grant nothing) --------------------------------------

    def _mirror(self, entity: dict, event: str) -> WebhookResult:
        """`authenticated` / `activated` / `updated`: mirror Razorpay's state.

        DELIBERATELY GRANTS NOTHING, including on `activated`. Razorpay marks a
        subscription active around its first charge, but the event that names
        the money is `subscription.charged`, and keeping one grant path is what
        makes double-granting impossible to reintroduce. A charge whose event
        was lost is recovered by the reconciler, not by widening this one.
        """
        subscription = self._resolve(entity)
        if subscription is None:
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        status = str(entity.get("status") or "")
        self.repository.sync_from_entity(
            subscription.subscription_id,
            status=status or None,
            paid_count=_int_or_none(entity.get("paid_count")),
            current_period_start=epoch_to_dt(entity.get("current_start")),
            current_period_end=epoch_to_dt(entity.get("current_end")),
            next_charge_at=epoch_to_dt(entity.get("charge_at")),
            activated_at=(self._now() if event == "subscription.activated"
                          and subscription.activated_at is None else None),
        )
        return WebhookResult(outcome=WebhookOutcome.STATE_SYNCED,
                             founder_id=subscription.founder_id)

    def _on_pending(self, entity: dict) -> WebhookResult:
        """A renewal charge failed and Razorpay is retrying it.

        Access is NOT touched. The founder still has grace time on the clock
        from their last successful charge, and Razorpay's retry schedule -- not
        ours -- decides what happens next (guide step 12). All this does is
        make the state visible, so the billing page can say "we couldn't take
        this month's payment" instead of looking normal until access vanishes.
        """
        subscription = self._resolve(entity)
        if subscription is None:
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        self.repository.sync_from_entity(
            subscription.subscription_id, status="pending",
            next_charge_at=epoch_to_dt(entity.get("charge_at")))
        logger.warning("payments: subscription renewal is pending after a failed charge",
                       extra={"founder_id": subscription.founder_id,
                              "subscription_id": subscription.subscription_id,
                              "access_until": subscription.access_until.isoformat()
                              if subscription.access_until else None})
        return WebhookResult(outcome=WebhookOutcome.FAILED_RECORDED,
                             founder_id=subscription.founder_id)

    def _on_halted(self, entity: dict) -> WebhookResult:
        """Razorpay has given up retrying. The grace window ends now.

        This is the one place access is shortened rather than extended: the
        founder has had their retries and their grace days, and no further
        money is coming. The sweep does the actual downgrade on its next run;
        truncating the clock here is what makes them eligible for it.
        """
        subscription = self._resolve(entity)
        if subscription is None:
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        now = self._now()
        self.repository.sync_from_entity(subscription.subscription_id, status="halted",
                                         commit=False)
        self.repository.set_access_until(subscription.subscription_id, now)
        logger.error("payments: subscription halted, paid access ends now",
                     extra={"founder_id": subscription.founder_id,
                            "subscription_id": subscription.subscription_id})
        return WebhookResult(outcome=WebhookOutcome.FAILED_RECORDED,
                             founder_id=subscription.founder_id)

    def _on_ended(self, entity: dict, event: str) -> WebhookResult:
        """`cancelled` or `completed` -- the mandate is over.

        Access runs to the end of the period already paid for, not to the
        moment the event arrived. A founder who cancels on the 2nd keeps what
        they bought until the 3rd; that is the promise the cancel screen makes,
        and this is where it is kept.
        """
        subscription = self._resolve(entity)
        if subscription is None:
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        now = self._now()
        status = "cancelled" if event == "subscription.cancelled" else "completed"
        period_end = epoch_to_dt(entity.get("current_end")) or subscription.current_period_end
        # Never EXTEND access here: a cancellation must not hand out the grace
        # days a successful charge would have. min() of what they already have
        # and the period they paid for.
        access_until = period_end or now
        if subscription.access_until is not None:
            access_until = min(subscription.access_until, access_until)

        self.repository.sync_from_entity(
            subscription.subscription_id, status=status, ended_at=now,
            cancelled_at=now if status == "cancelled" else None,
            current_period_end=period_end, commit=False)
        self.repository.set_access_until(subscription.subscription_id, access_until)

        logger.info("payments: subscription ended",
                    extra={"founder_id": subscription.founder_id, "status": status,
                           "access_until": access_until.isoformat() if access_until else None})
        return WebhookResult(outcome=WebhookOutcome.SUBSCRIPTION_ENDED,
                             founder_id=subscription.founder_id)

    # --- invoices -----------------------------------------------------------

    def _record_invoice(self, payload: dict) -> WebhookResult:
        """Persist the Razorpay invoice for a charge so the founder can find
        their receipt.

        The invoice is INDEXED here, not generated: Razorpay's document is the
        artefact, `invoice_url` points at it, and nothing in this codebase
        renders a competing one. `tax_amount_inr` is copied only if Razorpay
        reported it -- see guide step 14 and the migration docstring on why a
        tax number we invented would be worse than a null.
        """
        invoice = _entity(payload, "invoice")
        gateway_invoice_id = str(invoice.get("id") or "")
        if not gateway_invoice_id:
            return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT)

        gateway_subscription_id = invoice.get("subscription_id")
        subscription = None
        if gateway_subscription_id:
            subscription = self.repository.get_by_gateway_id(str(gateway_subscription_id))

        founder_id = subscription.founder_id if subscription else None
        if founder_id is None:
            # A one-time order's invoice: find the founder through the payment
            # row that order created.
            order_id = invoice.get("order_id")
            payment = (self.payments.get_by_gateway_order_id(str(order_id))
                       if order_id else None)
            founder_id = payment.founder_id if payment else None

        if founder_id is None:
            logger.error("payments: invoice for an unknown founder",
                         extra={"gateway_invoice_id": gateway_invoice_id})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        total_inr = _paise_to_inr(invoice.get("amount"), fallback=0)
        invoice_id = self.repository.upsert_invoice(
            founder_id=founder_id,
            subscription_id=subscription.subscription_id if subscription else None,
            gateway_invoice_id=gateway_invoice_id,
            gateway_order_id=invoice.get("order_id"),
            gateway_payment_id=invoice.get("payment_id"),
            gateway_subscription_id=str(gateway_subscription_id) if gateway_subscription_id
            else None,
            invoice_number=invoice.get("invoice_number") or invoice.get("receipt"),
            amount_inr=total_inr,
            tax_amount_inr=(_paise_to_inr(invoice.get("tax_amount"), fallback=None)
                            if invoice.get("tax_amount") is not None else None),
            total_amount_inr=total_inr,
            currency=str(invoice.get("currency") or _CURRENCY),
            status=str(invoice.get("status") or "paid"),
            invoice_url=invoice.get("short_url"),
            issued_at=epoch_to_dt(invoice.get("issued_at")),
            paid_at=epoch_to_dt(invoice.get("paid_at")),
            due_at=epoch_to_dt(invoice.get("expire_by")),
        )
        logger.info("payments: invoice recorded",
                    extra={"founder_id": founder_id, "invoice_id": invoice_id,
                           "gateway_invoice_id": gateway_invoice_id})
        return WebhookResult(outcome=WebhookOutcome.INVOICE_RECORDED, founder_id=founder_id)

    # --- reconciliation ------------------------------------------------------

    def reconcile(self, subscription: SubscriptionRecord) -> bool:
        """Ask Razorpay what it thinks, and catch up if a webhook was lost.

        The safety net behind having exactly one grant path. If Razorpay says
        it has charged more cycles than our row records, the founder paid for a
        month we never gave them -- so re-sync the dates and re-grant. It reads
        the subscription entity server-to-server, so nothing here trusts a
        delivery that never arrived.

        Returns True when something changed.
        """
        if self.gateway is None or not subscription.gateway_subscription_id:
            return False
        try:
            entity = self.gateway.fetch_subscription(subscription.gateway_subscription_id)
        except PaymentGatewayError as exc:
            logger.warning("payments: subscription reconcile could not reach the gateway",
                           extra={"subscription_id": subscription.subscription_id,
                                  "error": str(exc)})
            return False

        # The entity must be the one we asked about. The same guard
        # confirm_checkout makes before granting on a payment entity, and for
        # the same reason: this method re-grants a plan, so acting on an entity
        # that names a different subscription would grant one founder's month
        # to another. A correct gateway cannot return a mismatch -- which is
        # exactly why the check costs nothing and is worth having.
        remote_id = str(entity.get("id") or "")
        if remote_id and remote_id != subscription.gateway_subscription_id:
            logger.error("payments: reconcile received a different subscription than requested",
                         extra={"subscription_id": subscription.subscription_id,
                                "requested": subscription.gateway_subscription_id,
                                "received": remote_id})
            return False

        remote_paid = _int_or_none(entity.get("paid_count")) or 0
        status = str(entity.get("status") or "")
        period_end = epoch_to_dt(entity.get("current_end"))

        if remote_paid > subscription.paid_count and period_end:
            access_until = period_end + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
            self.repository.sync_from_entity(
                subscription.subscription_id, status=status or "active",
                paid_count=remote_paid,
                current_period_start=epoch_to_dt(entity.get("current_start")),
                current_period_end=period_end,
                next_charge_at=epoch_to_dt(entity.get("charge_at")), commit=False)
            self.repository.set_access_until(subscription.subscription_id, access_until)
            self.payments.grant_plan(subscription.founder_id, subscription.plan_type)
            logger.warning("payments: reconciled a subscription charge whose webhook was missed",
                           extra={"founder_id": subscription.founder_id,
                                  "subscription_id": subscription.subscription_id,
                                  "local_paid_count": subscription.paid_count,
                                  "remote_paid_count": remote_paid})
            return True

        if status and status != subscription.status:
            self.repository.sync_from_entity(subscription.subscription_id, status=status)
            return True
        return False

    # --- helpers -------------------------------------------------------------

    def _resolve(self, entity: dict) -> SubscriptionRecord | None:
        """Our row for the subscription this event names.

        A subscription id we never created is never acted on -- the same
        refusal `_grant_for_captured` makes for an unknown order, and for the
        same reason: granting on an entity that arrived from nowhere would be
        granting to nobody in particular.
        """
        gateway_subscription_id = entity.get("id")
        if not gateway_subscription_id:
            return None
        record = self.repository.get_by_gateway_id(str(gateway_subscription_id))
        if record is None:
            logger.error("payments: subscription event for an unknown subscription",
                         extra={"gateway_subscription_id": gateway_subscription_id})
        return record


def _entity(payload: dict, key: str) -> dict:
    """Razorpay nests every entity as `payload.<key>.entity`. Read defensively:
    a missing branch is an empty dict, never an AttributeError that turns a
    webhook into a 500 and an endless retry."""
    node = ((payload.get("payload") or {}).get(key) or {}).get("entity")
    return node if isinstance(node, dict) else {}


def _paise_to_inr(amount, *, fallback):
    """Razorpay talks paise; `payments.amount_inr` and `invoices.*_inr` are
    rupees. One conversion, so the two never disagree by a factor of 100."""
    if amount is None:
        return fallback
    try:
        return int(amount) / 100
    except (TypeError, ValueError):
        return fallback


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cancellation_reason_sql():
    from sqlalchemy import text
    return text("UPDATE subscriptions SET cancellation_reason = :reason "
                "WHERE subscription_id = :sid")
