"""Autopay subscriptions with a paid trial -- Razorpay Subscriptions.

THE OFFER. A trial coupon (coupons.trial_days, e.g. 100FOUNDERS) lets a
founder pay a small upfront fee (the coupon-discounted price, ₹11) for
`trial_days` of a plan, with an autopay mandate (UPI AutoPay / card /
eMandate) that charges the plan's full price (₹999) on the day after the trial
and every month after that, until they cancel.

HOW IT MAPS ONTO RAZORPAY. One Razorpay Plan per (tier, price, monthly),
created once and remembered in `gateway_plans`. Each trial is a Subscription
on it with `start_at` = end of trial and an upfront add-on for the fee: the
add-on is charged when the founder approves the mandate, the first plan charge
happens at `start_at`. Razorpay then drives the lifecycle through webhooks.

WHO DECIDES ACCESS. Never the browser. The founder's plan is granted when
Razorpay reports the mandate authenticated (webhook, or a confirm call that
re-reads the subscription from Razorpay server-to-server), extended on each
`subscription.charged`, and taken away by `expire_ended` once paid-for access
is over -- the first thing in this codebase that ever moves a founder back to
Free. That sweep only touches autopay subscriptions; one-time purchases are
unchanged.

IDEMPOTENCY. Razorpay redelivers. A trial is created once per gateway
subscription id (unique index); a recurring charge is recorded once per
gateway payment id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.logger import logger
from app.coupons.service import CouponService
from app.credits.models import CreditOperation
from app.credits.service import CreditService
from app.payments.errors import (
    InvalidCheckoutCallbackError,
    InvalidCheckoutError,
    PaymentGatewayUnavailableError,
    PaymentsNotConfiguredError,
)
from app.payments.gateway import PaymentGateway, PaymentGatewayError
from app.payments.models import WebhookOutcome, WebhookResult
from app.payments.subscription_repository import AutopaySubscription, SubscriptionRepository
from app.plans.catalog import PLANS, PlanTier
from app.plans.team import is_team_email

_SYSTEM_ADMIN_ID = 0
#: Monthly charges for ten years. Razorpay requires a finite count; nobody is
#: meant to reach it, and the founder can cancel at any point before.
_TOTAL_COUNT = 120
#: How long a live subscription keeps access past its paid-for end while a
#: renewal is in flight (UPI AutoPay announces a debit 24h ahead and may land
#: a day late). Past this, an unpaid renewal costs the plan.
RENEWAL_GRACE = timedelta(days=3)
#: How long a trial fee may sit `pending` before the reconcile sweep goes and
#: asks Razorpay what actually happened to it. Long enough that a founder still
#: on the mandate screen is not chased; short enough that a lost webhook costs
#: them minutes rather than their whole trial.
RECONCILE_AFTER = timedelta(minutes=10)
#: The "your trial ends soon" email goes out this far ahead of the first charge.
REMINDER_LEAD = timedelta(days=2)


class AutopayAlreadyActiveError(InvalidCheckoutError):
    def __init__(self):
        super().__init__("you already have an active autopay subscription")
        self.status_code = 409


class NoAutopaySubscriptionError(InvalidCheckoutError):
    def __init__(self):
        super().__init__("you have no active autopay subscription")
        self.status_code = 404


@dataclass(frozen=True)
class TrialSession:
    """What the browser needs to open Razorpay Checkout for the trial."""

    subscription_id: str
    key_id: str
    plan_tier: str
    upfront_paise: int
    recurring_paise: int
    trial_days: int
    trial_ends_at: datetime
    coupon_code: str


def _ts(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None
    except (TypeError, ValueError):
        return None


class SubscriptionService:
    def __init__(self, gateway: PaymentGateway | None, repository: SubscriptionRepository,
                 credits: CreditService, coupons: CouponService, *, clock=None):
        self.gateway = gateway
        self.repository = repository
        self.credits = credits
        self.coupons = coupons
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- founder-initiated -----------------------------------------------------

    def start_trial(self, founder_id: int, tier: PlanTier, coupon_code: str) -> TrialSession:
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        plan = PLANS.get(tier)
        if plan is None or not plan.is_paid or plan.one_time:
            raise InvalidCheckoutError("that plan can't be put on autopay")

        quote = self.coupons.quote(code=coupon_code, tier=tier, founder_id=founder_id)
        if not quote.trial_days:
            from app.coupons.errors import CouponNotTrialError
            raise CouponNotTrialError()
        if self.repository.live_for_founder(founder_id) is not None:
            raise AutopayAlreadyActiveError()

        now = self._now()
        trial_ends_at = now + timedelta(days=quote.trial_days)
        try:
            plan_id = self._gateway_plan_id(tier, plan.price_inr, plan.name)
            sub = self.gateway.create_subscription(
                plan_id=plan_id, start_at=int(trial_ends_at.timestamp()),
                total_count=_TOTAL_COUNT, upfront_paise=quote.payable_inr * 100,
                upfront_name=f"{quote.trial_days}-day {plan.name} trial",
                notes={"founder_id": str(founder_id), "plan_tier": tier.value,
                       "coupon": quote.code},
            )
        except PaymentGatewayError as exc:
            logger.error("subscriptions: could not create trial subscription",
                         extra={"founder_id": founder_id, "gateway_status": exc.status_code,
                                "gateway_message": exc.gateway_message, "error": str(exc)})
            raise PaymentGatewayUnavailableError() from exc

        gateway_sub_id = sub["id"]
        payment_id = self.repository.create_trial_payment(
            founder_id=founder_id, amount_inr=quote.payable_inr, plan_tier=tier.value,
            gateway_subscription_id=gateway_sub_id, list_amount_inr=quote.list_amount_inr,
            discount_inr=quote.discount_inr,
        )
        try:
            coupon, _ = self.coupons.reserve(code=coupon_code, tier=tier,
                                             founder_id=founder_id, payment_id=payment_id,
                                             for_trial=True)
        except Exception:
            # Nothing committed: no payment row, no slot. The subscription
            # at Razorpay was never authorised, so it charges nothing.
            self.repository.db.rollback()
            raise
        self.repository.attach_coupon(payment_id, coupon_id=coupon.coupon_id)
        logger.info("subscriptions: trial checkout started",
                    extra={"founder_id": founder_id, "subscription": gateway_sub_id,
                           "coupon": coupon.code, "upfront_inr": quote.payable_inr})
        return TrialSession(
            subscription_id=gateway_sub_id, key_id=self.gateway.key_id,
            plan_tier=tier.value, upfront_paise=quote.payable_inr * 100,
            recurring_paise=plan.price_inr * 100, trial_days=quote.trial_days,
            trial_ends_at=trial_ends_at, coupon_code=coupon.code,
        )

    def confirm_trial(self, founder_id: int, *, subscription_id: str, payment_id: str,
                      signature: str | None) -> WebhookResult:
        """The browser's "I approved autopay" -- verified, then settled by
        reading the subscription back from Razorpay, exactly as the webhook
        would. Whichever arrives first activates; the other is a no-op."""
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        pending = self.repository.pending_trial_payment(subscription_id)
        existing = self.repository.by_gateway_id(subscription_id)
        owner = (pending or {}).get("founder_id") or (existing.founder_id if existing else None)
        if owner != founder_id:
            raise InvalidCheckoutCallbackError()
        if existing is not None:
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=founder_id, plan=existing.plan_type)
        if signature and not self.gateway.verify_subscription_signature(
                subscription_id=subscription_id, payment_id=payment_id, signature=signature):
            raise InvalidCheckoutCallbackError()
        try:
            entity = self.gateway.fetch_subscription(subscription_id)
        except PaymentGatewayError as exc:
            raise PaymentGatewayUnavailableError() from exc
        status = entity.get("status")
        if status not in ("authenticated", "active"):
            # Logged, not silent. The browser fires this call without awaiting
            # it and discards the answer, so a founder whose mandate Razorpay
            # has not finished recording leaves no trace at all otherwise --
            # and if the webhook is also lost, nothing downstream ever asks
            # again. `reconcile_unsettled_trials` is what picks them up; this
            # line is how anyone finds out it had to.
            logger.warning("subscriptions: trial confirm found no live mandate yet",
                           extra={"founder_id": founder_id, "subscription": subscription_id,
                                  "gateway_status": status})
            return WebhookResult(outcome=WebhookOutcome.NOT_CAPTURED, founder_id=founder_id)
        return self._activate_trial(entity, gateway_payment_id=payment_id)

    def cancel(self, founder_id: int) -> AutopaySubscription:
        """Stop autopay. Access runs to the end of what has been paid for --
        the trial, or the current month -- and is then removed by the sweep."""
        if self.gateway is None:
            raise PaymentsNotConfiguredError()
        sub = self.repository.live_for_founder(founder_id)
        if sub is None:
            raise NoAutopaySubscriptionError()
        # Before the first plan charge there is no billing cycle to finish, so
        # Razorpay cancels outright; after it, cancel at cycle end so the month
        # already paid for is not cut short at Razorpay's side either.
        in_trial = sub.status == "trial"
        try:
            self.gateway.cancel_subscription(sub.gateway_subscription_id,
                                             at_cycle_end=not in_trial)
        except PaymentGatewayError as exc:
            logger.error("subscriptions: cancel failed at gateway",
                         extra={"founder_id": founder_id, "error": str(exc),
                                "subscription": sub.gateway_subscription_id})
            raise PaymentGatewayUnavailableError() from exc
        now = self._now()
        self.repository.update_subscription(
            sub.subscription_id, status="cancelled", cancelled_at=now,
            cancellation_reason="cancelled by founder")
        logger.info("subscriptions: autopay cancelled by founder",
                    extra={"founder_id": founder_id, "access_until": str(sub.expires_at)})
        return self.repository.by_gateway_id(sub.gateway_subscription_id)

    # --- Razorpay events -----------------------------------------------------------

    def handle_event(self, event: str, payload: dict) -> WebhookResult:
        body = payload.get("payload") or {}
        sub = (body.get("subscription") or {}).get("entity") or {}
        payment = (body.get("payment") or {}).get("entity") or {}
        gid = sub.get("id")
        if not gid:
            return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT)

        if event == "subscription.authenticated":
            return self._activate_trial(sub, gateway_payment_id=payment.get("id"))
        if event == "subscription.charged":
            return self._record_charge(sub, payment)

        local = self.repository.by_gateway_id(gid)
        if local is None:
            # A lifecycle event for a subscription this app never activated
            # (e.g. one created by hand in the dashboard). Nothing to change.
            logger.info("subscriptions: event for unknown subscription",
                        extra={"event": event, "subscription": gid})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        now = self._now()
        if event in ("subscription.activated", "subscription.resumed"):
            if local.status not in ("cancelled",):
                self.repository.update_subscription(local.subscription_id, status="active")
        elif event == "subscription.halted":
            # Repeated charge failures. Access lasts to what was paid for.
            self.repository.update_subscription(local.subscription_id, status="halted")
        elif event == "subscription.cancelled":
            self.repository.update_subscription(
                local.subscription_id, status="cancelled",
                cancelled_at=local.cancelled_at or now,
                cancellation_reason="cancelled (gateway)")
        elif event == "subscription.completed":
            self.repository.update_subscription(local.subscription_id, status="cancelled",
                                                cancelled_at=local.cancelled_at or now,
                                                cancellation_reason="completed")
        elif event == "subscription.paused":
            self.repository.update_subscription(local.subscription_id, status="paused")
        else:
            # subscription.pending (a charge failed and is being retried) and
            # anything newer: the founder keeps access while Razorpay retries.
            return WebhookResult(outcome=WebhookOutcome.IGNORED_EVENT,
                                 founder_id=local.founder_id)
        logger.info("subscriptions: lifecycle event applied",
                    extra={"event": event, "subscription": gid, "founder_id": local.founder_id})
        return WebhookResult(outcome=WebhookOutcome.CAPTURED if event.endswith(
            ("activated", "resumed")) else WebhookOutcome.FAILED_RECORDED,
            founder_id=local.founder_id, plan=local.plan_type)

    # --- grants --------------------------------------------------------------------

    def _activate_trial(self, sub: dict, *, gateway_payment_id: str | None) -> WebhookResult:
        gid = sub.get("id")
        existing = self.repository.by_gateway_id(gid)
        if existing is not None:
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=existing.founder_id, plan=existing.plan_type)
        pending = self.repository.pending_trial_payment(gid)
        if pending is None:
            logger.error("subscriptions: authenticated subscription with no trial payment",
                         extra={"subscription": gid})
            return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)

        founder_id = pending["founder_id"]
        tier = PlanTier(pending["plan_tier"])
        plan = PLANS[tier]
        now = self._now()
        trial_ends_at = _ts(sub.get("start_at")) or now
        try:
            subscription_id = self.repository.create_trial_subscription(
                founder_id=founder_id, plan_type=tier.value, amount_inr=plan.price_inr,
                gateway_subscription_id=gid, started_at=now, trial_ends_at=trial_ends_at)
            self.repository.set_plan(founder_id, tier.value, commit=False)
            self.repository.db.commit()
        except IntegrityError:
            # The webhook and the confirm call raced; the other one won.
            self.repository.db.rollback()
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=founder_id, plan=tier.value)
        self.repository.mark_payment_success(
            pending["payment_id"], gateway_payment_id=gateway_payment_id, paid_at=now,
            subscription_id=subscription_id)
        try:
            self.coupons.repository.confirm_for_payment(pending["payment_id"], at=now)
            self.repository.db.commit()
        except Exception as exc:  # noqa: BLE001 -- the grant above must stand
            logger.error("subscriptions: trial granted but coupon not confirmed",
                         extra={"payment_id": pending["payment_id"], "error": str(exc)})
        self._grant_credits(founder_id, plan, f"{plan.name} trial started ({gid})")
        logger.info("subscriptions: trial activated",
                    extra={"founder_id": founder_id, "subscription": gid,
                           "trial_ends_at": trial_ends_at.isoformat()})
        return WebhookResult(outcome=WebhookOutcome.CAPTURED, payment_id=pending["payment_id"],
                             founder_id=founder_id, plan=tier.value, granted_at=now)

    def _record_charge(self, sub: dict, payment: dict) -> WebhookResult:
        gid = sub.get("id")
        gpid = payment.get("id")
        local = self.repository.by_gateway_id(gid)
        if local is None:
            if sub.get("status") in ("authenticated", "active"):
                # The charge arrived before the authentication event; activate
                # first, then record this charge against it.
                result = self._activate_trial(sub, gateway_payment_id=None)
                local = self.repository.by_gateway_id(gid)
                if local is None:
                    return result
            else:
                return WebhookResult(outcome=WebhookOutcome.UNKNOWN_PAYMENT)
        if not gpid or self.repository.payment_recorded(gpid):
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=local.founder_id, plan=local.plan_type)

        amount_inr = int(payment.get("amount") or 0) // 100
        plan = PLANS[PlanTier(local.plan_type)]
        if amount_inr < plan.price_inr:
            # The trial's upfront fee, reported as a charge. Already counted
            # when the trial was activated; just note which payment it was.
            pending = self.repository.pending_trial_payment(gid)
            if pending is not None:
                self.repository.mark_payment_success(
                    pending["payment_id"], gateway_payment_id=gpid, paid_at=self._now(),
                    subscription_id=local.subscription_id)
            return WebhookResult(outcome=WebhookOutcome.ALREADY_PROCESSED,
                                 founder_id=local.founder_id, plan=local.plan_type)

        now = self._now()
        paid_until = _ts(sub.get("current_end")) or now + timedelta(days=31)
        self.repository.record_recurring_payment(
            founder_id=local.founder_id, amount_inr=amount_inr, plan_tier=local.plan_type,
            gateway_payment_id=gpid, gateway_subscription_id=gid,
            subscription_id=local.subscription_id, paid_at=now)
        status = "cancelled" if local.status == "cancelled" else "active"
        self.repository.update_subscription(local.subscription_id, status=status,
                                            expires_at=paid_until)
        self.repository.set_plan(local.founder_id, local.plan_type)
        self._grant_credits(local.founder_id, plan, f"{plan.name} renewal ({gpid})")
        logger.info("subscriptions: recurring charge recorded",
                    extra={"founder_id": local.founder_id, "subscription": gid,
                           "amount_inr": amount_inr, "paid_until": paid_until.isoformat()})
        return WebhookResult(outcome=WebhookOutcome.CAPTURED, founder_id=local.founder_id,
                             plan=local.plan_type, granted_at=now)

    def _grant_credits(self, founder_id: int, plan, reason: str) -> None:
        if not plan.monthly_credits:
            return
        try:
            self.credits.adjust(founder_id, admin_id=_SYSTEM_ADMIN_ID,
                                operation=CreditOperation.ADD, amount=plan.monthly_credits,
                                reason=reason)
        except Exception as exc:  # noqa: BLE001 -- the plan grant must stand
            logger.error("subscriptions: plan granted but credit grant failed",
                         extra={"founder_id": founder_id, "error": str(exc)})

    def _gateway_plan_id(self, tier: PlanTier, price_inr: int, name: str) -> str:
        plan_id = self.repository.get_gateway_plan(tier=tier.value, amount_inr=price_inr,
                                                   period="monthly")
        if plan_id:
            return plan_id
        created = self.gateway.create_plan(
            amount_paise=price_inr * 100, period="monthly", interval=1,
            name=f"Ally {name} (monthly)", notes={"plan_tier": tier.value})
        return self.repository.save_gateway_plan(gateway_plan_id=created, tier=tier.value,
                                                 amount_inr=price_inr, period="monthly")

    # --- sweeps ----------------------------------------------------------------------

    def reconcile_unsettled_trials(self, *, limit: int = 50) -> dict:
        """Activate trials Razorpay authorised but nothing told us about.

        WHY THIS EXISTS. Activation had two paths and no third: the
        `subscription.authenticated` webhook, and the browser calling
        /trial/confirm straight after the mandate is approved. Each is a good
        path and either alone is enough -- but they share a failure mode. The
        webhook depends on dashboard configuration this app cannot see, and
        the browser call is fired and deliberately not awaited (Billing.jsx
        swallows its rejection, because normally the webhook is the backstop).
        Lose both and the founder has paid, Razorpay holds a live mandate, and
        this system holds a `pending` payment row it will never look at again.

        Observed in production on the first real ₹11 trial: payment taken,
        autopay mandate authorised, founder left on Free, and nothing anywhere
        reporting a problem. Recurring charges already had this safety net --
        `subscription.charged` is reconciled by nobody, but a missed one only
        shortens access, where a missed activation denies it outright.

        So: ask Razorpay. It is the only party that actually knows, and
        `fetch_subscription` is the same server-to-server read /trial/confirm
        makes. A subscription Razorpay reports as `authenticated` or `active`
        is one the founder paid for, whatever this app did or did not hear.

        Safe to run on a schedule and safe to run twice: `_activate_trial`
        returns ALREADY_PROCESSED for a subscription that has a local row, and
        the unique index on gateway_subscription_id settles any race with a
        webhook arriving at the same moment.

        One founder's bad row never stops the sweep -- a gateway error or an
        unexpected status is counted and stepped over, because the next
        founder in the list is also waiting for a plan they paid for.
        """
        if self.gateway is None:
            return {"checked": 0, "activated": 0, "not_ready": 0, "errors": 0}

        cutoff = self._now() - RECONCILE_AFTER
        rows = self.repository.unsettled_trial_payments(older_than=cutoff, limit=limit)
        checked = activated = not_ready = errors = 0

        for row in rows:
            gid = row["gateway_subscription_id"]
            checked += 1
            try:
                entity = self.gateway.fetch_subscription(gid)
            except PaymentGatewayError as exc:
                errors += 1
                logger.warning(
                    "subscriptions: could not re-read an unsettled trial",
                    extra={"subscription": gid, "founder_id": row["founder_id"],
                           "gateway_status": exc.status_code, "error": str(exc)})
                continue

            status = entity.get("status")
            if status not in ("authenticated", "active"):
                # Created but never approved, or already dead. Not ours to
                # grant -- `expire_ended` and the coupon TTL clean these up.
                not_ready += 1
                continue

            try:
                # No gateway_payment_id: the add-on charge is not named on the
                # subscription entity, and the payment row is better marked
                # paid with it unknown than left pending with it missing. A
                # later webhook carrying the id updates nothing -- the row is
                # already settled -- which is the right trade.
                result = self._activate_trial(entity, gateway_payment_id=None)
            except Exception as exc:                       # noqa: BLE001
                errors += 1
                self.repository.db.rollback()
                logger.error("subscriptions: reconcile could not activate a trial",
                             extra={"subscription": gid,
                                    "founder_id": row["founder_id"], "error": str(exc)})
                continue

            if result.outcome is WebhookOutcome.CAPTURED:
                activated += 1
                logger.warning(
                    "subscriptions: trial activated by reconcile, not by webhook",
                    extra={"subscription": gid, "founder_id": row["founder_id"],
                           "paid_at": row["created_at"].isoformat()
                                      if row.get("created_at") else None})

        if activated:
            logger.warning("subscriptions: reconcile rescued paid trials",
                           extra={"activated": activated, "checked": checked})
        return {"checked": checked, "activated": activated,
                "not_ready": not_ready, "errors": errors}

    def expire_ended(self) -> dict:
        """Move founders whose autopay access has ended back to Free.

        Team accounts are left alone -- they are held at Pro on every request
        anyway (plans/team.py) -- and so is anyone who still holds the plan
        through another live purchase.
        """
        now = self._now()
        expired = skipped = 0
        for sub in self.repository.ended_access(now=now, live_grace_until=now - RENEWAL_GRACE):
            self.repository.update_subscription(
                sub.subscription_id, status="expired",
                cancelled_at=sub.cancelled_at or now,
                cancellation_reason=None if sub.status in ("cancelled", "halted")
                else "renewal not received")
            email, _ = self.repository.founder_email(sub.founder_id)
            if is_team_email(email) or self.repository.other_live_access(
                    sub.founder_id, excluding=sub.subscription_id, now=now):
                skipped += 1
                continue
            self.repository.set_plan(sub.founder_id, PlanTier.FREE.value)
            expired += 1
            logger.info("subscriptions: access ended, moved to Free",
                        extra={"founder_id": sub.founder_id,
                               "subscription": sub.gateway_subscription_id,
                               "was": sub.status})
        return {"expired": expired, "kept_other_access": skipped}

    def send_trial_reminders(self, send_email, notify=None) -> dict:
        """One email per trial, `REMINDER_LEAD` before the first charge."""
        now = self._now()
        sent = 0
        for sub in self.repository.trials_needing_reminder(now=now, until=now + REMINDER_LEAD):
            email, name = self.repository.founder_email(sub.founder_id)
            plan = PLANS[PlanTier(sub.plan_type)]
            when = sub.trial_ends_at.strftime("%-d %B %Y")
            subject = f"Your Ally {plan.name} trial ends on {when}"
            body = (
                f"Hi {name or 'there'},\n\n"
                f"Your {plan.name} trial ends on {when}. On that day autopay will charge "
                f"₹{plan.price_inr:,} for your next month of Ally {plan.name}, and then "
                f"₹{plan.price_inr:,} each month until you cancel.\n\n"
                "Want to keep going? You don't need to do anything.\n"
                "Not for you? Cancel before then from Billing in the app "
                "(https://app.goxlally.ai/app/billing) and you won't be charged.\n\n"
                "-- Team GoXL"
            )
            delivered = bool(email) and send_email(email, subject, body)
            if notify is not None:
                try:
                    notify(sub.founder_id, title=subject,
                           body=f"Autopay charges ₹{plan.price_inr:,} on {when}. "
                                "Cancel anytime before then from Billing.",
                           dedup_key=f"trial_ending:{sub.gateway_subscription_id}")
                except Exception as exc:  # noqa: BLE001 -- the email is what matters
                    logger.warning("subscriptions: trial reminder bell failed",
                                   extra={"error": str(exc)})
            self.repository.update_subscription(sub.subscription_id, reminder_sent_at=now)
            sent += int(bool(delivered))
        return {"reminders_sent": sent}
