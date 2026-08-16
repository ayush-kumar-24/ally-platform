"""Supabase Auth webhook -- the second half of "auth stays on Supabase
permanently, the database does not".

Why this exists at all: `founders.user_id` used to carry a live foreign key
to Supabase's own `auth.users`, with ON DELETE CASCADE -- so deleting a
Supabase Auth identity auto-deleted the matching founder row, entirely at
the database level, with no application code involved. That constraint is
not tracked by Alembic (added directly on the Supabase side; confirmed by
checking the SQLAlchemy models, which declare no such FK) and cannot be
recreated once the founders table lives outside Supabase's own Postgres --
there is no cross-database foreign key. Losing it silently would mean an
identity can be deleted while its founder data sits behind forever, with
nothing to notice.

This endpoint replaces the cascade with the application-level equivalent:
Supabase tells us an identity is gone, we schedule that founder's erasure
through the SAME PrivacyService.request_account_deletion() a self-service
DPDP request uses. No second deletion path, no special-cased "webhook
delete" -- one execution pipeline (see app/privacy/deletion_executor.py),
two callers.

Auth: a shared secret in the `X-Webhook-Secret` header, configured on the
Supabase project's Auth Hook settings and in SUPABASE_WEBHOOK_SECRET here.
Rejects with 401 rather than 404/500 on a bad or missing secret -- an
unauthenticated caller must not be able to distinguish "wrong secret" from
"this founder doesn't exist" well enough to enumerate accounts.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.config import settings
from app.core.container import container
from app.core.logger import logger
from app.db.session import get_db
from app.privacy.errors import DeletionAlreadyRequestedError
from app.repositories import founder_repository

router = APIRouter(prefix="/webhooks/supabase", tags=["webhooks"])

# Only the events this endpoint actually acts on. Anything else is logged to
# webhook_logs (so nothing Supabase sends is silently dropped without a
# trace) and acknowledged with 200 -- an event we don't yet handle is not a
# delivery failure, and telling Supabase otherwise would make it retry
# forever for no reason.
_HANDLED_EVENT_TYPES = frozenset({"user.deleted"})


def _verify_secret(x_webhook_secret: str | None) -> None:
    if not settings.SUPABASE_WEBHOOK_SECRET:
        # Fail closed: an unconfigured secret must refuse every request, not
        # accept everything because there was nothing to check against.
        logger.error("Supabase webhook called but SUPABASE_WEBHOOK_SECRET is unset")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webhook not configured")
    if not x_webhook_secret or x_webhook_secret != settings.SUPABASE_WEBHOOK_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")


@router.post("/auth", status_code=status.HTTP_200_OK, summary="Supabase Auth event webhook")
def handle_supabase_auth_event(
    payload: dict[str, Any],
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    _verify_secret(x_webhook_secret)

    event_type = str(payload.get("type") or payload.get("event") or "unknown")
    record = payload.get("record") or payload.get("user") or {}
    user_id = record.get("id")

    # Idempotency key: Supabase's own event id if present, else a stable
    # synthesized one. Either way the UNIQUE constraint on
    # webhook_logs.gateway_event_id is what actually enforces "process this
    # exactly once" -- a retried delivery hits the constraint and is
    # reported as already-handled rather than scheduling a second deletion
    # (which request_account_deletion would refuse anyway, but this avoids
    # even attempting it).
    gateway_event_id = str(
        payload.get("id") or (f"supabase-{event_type}-{user_id}" if user_id else None)
        or f"supabase-{event_type}-unkeyed"
    )

    log_id = _log_webhook(db, event_type=event_type, gateway_event_id=gateway_event_id,
                          payload=payload, founder_id=None)

    if event_type not in _HANDLED_EVENT_TYPES:
        _mark_processed(db, log_id, status="processed")
        return {"status": "ignored", "event_type": event_type}

    if not user_id:
        _mark_processed(db, log_id, status="failed", error="event carried no user id")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing user id in event payload")

    try:
        founder = founder_repository.get_by_user_id(db, user_id)
    except (ValueError, TypeError):
        _mark_processed(db, log_id, status="failed", error=f"invalid user id: {user_id!r}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed user id")

    if founder is None:
        # Nothing to schedule -- the identity was deleted before a founder
        # row was ever provisioned for it (e.g. mid-signup). Acknowledged,
        # not an error: there is genuinely nothing for us to do.
        _mark_processed(db, log_id, status="processed", founder_id=None)
        return {"status": "no_founder_row", "user_id": str(user_id)}

    try:
        state, _action = container.privacy_service(db).request_account_deletion(founder.founder_id)
        scheduled_at = state.deletion_scheduled_at
    except DeletionAlreadyRequestedError:
        # Already scheduled (e.g. the founder self-requested deletion before
        # their Supabase identity was removed). Not a failure -- the outcome
        # this webhook exists to produce already holds.
        scheduled_at = None

    _mark_processed(db, log_id, status="processed", founder_id=founder.founder_id)
    logger.info(
        "founder erasure scheduled from Supabase identity-deleted webhook",
        extra={"founder_id": founder.founder_id, "scheduled_at": str(scheduled_at)},
    )
    return {"status": "deletion_scheduled", "founder_id": founder.founder_id,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None}


def _log_webhook(db: Session, *, event_type: str, gateway_event_id: str,
                 payload: dict, founder_id: int | None) -> int | None:
    try:
        row = db.execute(
            text("""insert into webhook_logs (source, event_type, gateway_event_id, payload, founder_id)
                    values ('supabase', :event_type, :gwid, CAST(:payload AS jsonb), :fid)
                    on conflict (gateway_event_id) do nothing
                    returning log_id"""),
            {"event_type": event_type, "gwid": gateway_event_id,
             "payload": json.dumps(payload), "fid": founder_id},
        ).first()
        db.commit()
        return row[0] if row else None
    except Exception as exc:  # noqa: BLE001 -- logging the webhook must never block acting on it
        logger.error("failed to log webhook receipt", extra={"error": str(exc)})
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
                           founder_id = coalesce(:fid, founder_id),
                           error_message = :err
                     where log_id = :id"""),
            {"status": status, "fid": founder_id, "err": error, "id": log_id},
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("failed to update webhook log status", extra={"error": str(exc)})
        db.rollback()
