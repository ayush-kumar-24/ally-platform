"""Razorpay payment webhook -- the only path that actually grants a plan.

    POST /webhooks/razorpay

Authenticated by Razorpay's own HMAC-SHA256 body signature (X-Razorpay-Signature,
verified against RAZORPAY_WEBHOOK_SECRET -- see app/payments/gateway.py), not a
founder or admin token: nothing about this request carries a founder's identity
except what Razorpay itself reports inside the signed payload.

Logged to webhook_logs the same way app/api/v1/webhooks/supabase.py already
does (source='razorpay' is literally in that table's own CHECK constraint,
webhook_logs_source_check -- this endpoint is what that constraint was
seeded for). The UNIQUE constraint on gateway_event_id is a second,
DB-level idempotency guard alongside PaymentService's own check against
payments.gateway_payment_id; either one alone would be enough, both cost
nothing extra.

Every outcome except a bad signature returns 200 -- Razorpay retries on
anything else, and "we don't handle this event type" or "we don't recognise
this order" are not delivery failures worth retrying forever for.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.container import container
from app.core.logger import logger
from app.db.session import get_db
from app.payments.errors import InvalidWebhookSignatureError, PaymentsNotConfiguredError
from app.payments.models import WebhookOutcome

router = APIRouter(prefix="/webhooks/razorpay", tags=["webhooks"])


@router.post("", summary="Razorpay payment event webhook")
async def handle_razorpay_event(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {}
    event = str(payload.get("event") or "unknown")
    entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    gateway_event_id = str(entity.get("id") or f"razorpay-{event}-unkeyed")

    log_id = _log_webhook(db, event_type=event, gateway_event_id=gateway_event_id, payload=payload)

    try:
        result = container.payment_service(db).handle_webhook(
            body=body, signature=x_razorpay_signature or "")
    except InvalidWebhookSignatureError:
        _mark_processed(db, log_id, status="failed", error="invalid signature")
        raise
    except PaymentsNotConfiguredError:
        _mark_processed(db, log_id, status="failed", error="payments not configured")
        raise
    except Exception as exc:  # noqa: BLE001 -- must still ack the log row, then re-raise
        _mark_processed(db, log_id, status="failed", error=str(exc))
        raise

    _mark_processed(
        db, log_id, status="processed" if result.outcome != WebhookOutcome.UNKNOWN_PAYMENT
        else "failed",
        founder_id=result.founder_id,
        error=None if result.outcome != WebhookOutcome.UNKNOWN_PAYMENT else "unknown order/payment",
    )

    if result.outcome == WebhookOutcome.CAPTURED:
        logger.info("razorpay webhook: plan granted", extra={"founder_id": result.founder_id,
                                                              "plan": result.plan})

    return {"outcome": result.outcome, "payment_id": result.payment_id}


def _log_webhook(db: Session, *, event_type: str, gateway_event_id: str, payload: dict) -> int | None:
    try:
        row = db.execute(
            text("""insert into webhook_logs (source, event_type, gateway_event_id, payload)
                    values ('razorpay', :event_type, :gwid, CAST(:payload AS jsonb))
                    on conflict (gateway_event_id) do nothing
                    returning log_id"""),
            {"event_type": event_type, "gwid": gateway_event_id, "payload": json.dumps(payload)},
        ).first()
        db.commit()
        return row[0] if row else None
    except Exception as exc:  # noqa: BLE001 -- logging the webhook must never block acting on it
        logger.error("failed to log razorpay webhook receipt", extra={"error": str(exc)})
        db.rollback()
        return None


def _mark_processed(db: Session, log_id: int | None, *, status: str,
                    founder_id: int | None = None, error: str | None = None) -> None:
    if log_id is None:
        return
    try:
        db.execute(
            text("""update webhook_logs
                       set status = :status, processed_at = now(),
                           founder_id = coalesce(:fid, founder_id), error_message = :error
                     where log_id = :log_id"""),
            {"status": status, "fid": founder_id, "error": error, "log_id": log_id},
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("failed to mark razorpay webhook processed", extra={"error": str(exc)})
        db.rollback()
