"""Inbound webhooks -- transport only, secret-authenticated (see deps.py).

    POST /webhooks/supabase/auth-user-deleted   Supabase Auth account deleted -> erase now
    POST /webhooks/deletion-sweep               run the scheduled-erasure sweep now

Both exist because this backend runs as a persistent container (App Runner /
Railway / Render -- see DEPLOY.md) with no in-process scheduler, and the live
Supabase project does not have `pg_cron` installed. The sweep is therefore driven
from OUTSIDE the process: point an external scheduler (a GitHub Actions cron
workflow, a Render/Railway Cron Job, or `pg_cron` + `pg_net` if it is ever enabled
on the Supabase project) at /deletion-sweep on an interval. `scripts/run_deletion_sweep.py`
does the same thing without HTTP, for a scheduler that can exec into the container.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.webhooks.deps import verify_webhook_secret
from app.api.v1.webhooks.schemas import SupabaseAuthWebhookPayload
from app.core.container import container
from app.db.session import get_db
from app.repositories.founder import FounderRepository

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_founders = FounderRepository()


@router.post("/supabase/auth-user-deleted", response_model=dict,
             summary="Supabase Auth account deleted -- erase the matching founder now",
             dependencies=[Depends(verify_webhook_secret)])
def auth_user_deleted(payload: SupabaseAuthWebhookPayload, db: Session = Depends(get_db)) -> dict:
    old = payload.old_record or {}
    user_id = old.get("id")
    if not user_id:
        # Not a deletion this webhook cares about (Supabase also fires this same
        # endpoint's trigger config for other row events if misconfigured) --
        # acknowledge rather than error, so Supabase does not retry forever.
        return {"handled": False, "reason": "no old_record.id in payload"}

    founder = _founders.get_by_user_id(db, user_id)
    if founder is None:
        return {"handled": False, "reason": "no founder for this auth user"}

    outcome = container.deletion_executor(db).execute_now(founder.founder_id)
    return {
        "handled": True,
        "founder_id": founder.founder_id,
        "succeeded": outcome.succeeded,
        "data_types_deleted": outcome.data_types_deleted,
        "error": outcome.error,
    }


@router.post("/deletion-sweep", response_model=dict,
             summary="Run the scheduled account-deletion sweep",
             dependencies=[Depends(verify_webhook_secret)])
def deletion_sweep(batch_size: int = 50, db: Session = Depends(get_db)) -> dict:
    summary = container.deletion_executor(db).run_due(batch_size=batch_size)
    return {
        "checked": summary.checked,
        "succeeded": summary.succeeded_count,
        "failed": summary.failed_count,
        "failed_founder_ids": [o.founder_id for o in summary.failed],
    }
