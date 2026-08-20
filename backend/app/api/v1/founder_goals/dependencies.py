"""Founder Goals API dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.founder_goals.service import FounderGoalService
from app.models import Founder


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_founder_goal_service(db: Session = Depends(get_db)) -> FounderGoalService:
    return container.founder_goal_service(db)
