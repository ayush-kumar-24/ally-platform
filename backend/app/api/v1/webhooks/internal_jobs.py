"""Internal-only endpoint an external scheduler calls to run the account-
deletion sweep -- the consumer side of deletion_scheduled_at that never
existed before.

Why an HTTP endpoint and not a Celery task: there is no task-queue
infrastructure in this codebase (checked -- no Celery import, no worker
process, no Redis usage anywhere in app/, despite being listed as part of
the intended stack). Building that out is a bigger decision than this one
job justifies. This matches the pattern the RDS migration brief already
assumes for `create_next_month_partitions()` -- "EventBridge + Lambda, or
pg_cron if enabled" calling a plain callable on a schedule -- so a protected
endpoint any of those can hit is the option that doesn't invent new
infrastructure or contradict a decision already being made elsewhere.

No founder is present in this request at all -- authenticated by a shared
secret (X-Internal-Secret / INTERNAL_JOBS_SECRET), not a founder or admin
token. Idempotent: re-running finds nothing new to do, because
find_due_for_deletion() only returns founders whose deletion_executed_at is
still NULL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.db.session import get_db
from app.privacy.db_repository import SqlAlchemyPrivacyRepository
from app.privacy.deletion_executor import AccountDeletionExecutor

router = APIRouter(prefix="/internal/jobs", tags=["internal"])


def _verify_secret(x_internal_secret: str | None) -> None:
    if not settings.INTERNAL_JOBS_SECRET:
        logger.error("internal jobs endpoint called but INTERNAL_JOBS_SECRET is unset")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Internal jobs not configured")
    if not x_internal_secret or x_internal_secret != settings.INTERNAL_JOBS_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal secret")


@router.post("/process-deletions", summary="Run the account-erasure sweep for due founders")
def process_deletions(
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    _verify_secret(x_internal_secret)

    from datetime import datetime, timezone

    repo = SqlAlchemyPrivacyRepository(db)
    executor = AccountDeletionExecutor(db)
    now = datetime.now(timezone.utc)

    due = repo.find_due_for_deletion(now)
    results = []
    for founder_id in due:
        try:
            result = executor.run(founder_id)
            results.append({"founder_id": founder_id, "status": "executed",
                            "tables_touched": len(result.hard_deleted)})
        except Exception as exc:  # noqa: BLE001 -- one founder's failure must not stop the sweep
            logger.error("deletion execution failed for one founder, continuing sweep",
                        extra={"founder_id": founder_id, "error": str(exc)})
            db.rollback()
            results.append({"founder_id": founder_id, "status": "failed", "error": str(exc)})

    return {"due_count": len(due), "results": results}
