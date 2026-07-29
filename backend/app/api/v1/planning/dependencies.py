"""Planning API dependencies.

The service comes from the container (DB-backed). `get_diagnosis_steps` composes the
frozen M1 context builder read-only to fetch the founder's next steps for seeding.
Tests override all three.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.planning.service import PlanningService


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_planning_service(db: Session = Depends(get_db)) -> PlanningService:
    return container.planning_service(db)


def get_diagnosis_steps(
    founder_id: int = Depends(get_current_founder_id),
    db: Session = Depends(get_db),
) -> list[str]:
    """Read-only compose of the frozen diagnosis: next_steps + priority_actions.
    Never modifies Phase 5. Empty when the founder has no diagnosis."""
    from app.api.v1.ally.context.builder import AllyContextBuilder
    from app.api.v1.ally.context.repository import AllyContextRepository

    context = AllyContextBuilder(AllyContextRepository(db)).build(founder_id)
    diagnosis = context.diagnosis
    if diagnosis is None:
        return []
    return [*diagnosis.next_steps, *diagnosis.priority_actions]
