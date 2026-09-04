"""Founder Goals API dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.founder_goals.service import FounderGoalService
from app.models import Founder
from app.plans.catalog import Feature


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_founder_goal_service(db: Session = Depends(get_db)) -> FounderGoalService:
    return container.founder_goal_service(db)


def require_goals(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> None:
    """Goals is a Rs 450 feature. Rs 199 buys the diagnosis and the report it
    writes; the place to act on it starts one tier up.

    Applied once at the router rather than per endpoint, for the same reason
    planning and vision do it: a route added later is then protected by
    default instead of by the author remembering.
    """
    container.entitlement_service(db).require_feature(
        founder.plan_type, Feature.GOALS
    )
