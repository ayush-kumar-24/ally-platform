"""Task-oriented LLM factory -- the ONE entry point engines use.

Engines call `provider_for_task(db, LLMTask.X)` and get a ready provider: the
model is resolved from the DB (task->model routing), the concrete adapter comes
from the registry (nothing vendor-specific leaks here), and every call is logged
to llm_call_log. Adding a cheaper model for a task later is a DB UPDATE -- no
engine code changes.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.llm.base import LLMProvider
from app.services.llm.registry import get_provider
from app.services.llm.router import LLMTask, TaskModel, resolve_task_model
from app.services.llm.telemetry import LoggingLLMProvider

__all__ = ["LLMTask", "TaskModel", "provider_for_task"]


def provider_for_task(
    db: Session,
    task: str,
    *,
    founder_id: int | None = None,
    session_id: int | None = None,
) -> LLMProvider:
    """Build the telemetry-wrapped provider that serves `task`, per DB routing."""
    tm = resolve_task_model(db, task)
    base = get_provider(tm.provider)

    founder_uuid = db.info.get("current_founder_uuid")
    if founder_id is None and founder_uuid:
        founder_id = db.execute(text("SELECT get_founder_id()")).scalar_one_or_none()
    # Pin the resolved model; providers build fresh per resolve, so this is safe.
    if hasattr(base, "with_model"):
        base = base.with_model(tm.model_id)
    return LoggingLLMProvider(
        base,
        task=task,
        provider=tm.provider,
        model_id=tm.model_id,
        founder_id=founder_id,
        founder_uuid=founder_uuid,
        session_id=session_id,
    )
