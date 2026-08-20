"""Achievements API dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.achievements.service import AchievementService
from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_achievement_service(db: Session = Depends(get_db)) -> AchievementService:
    return container.achievement_service(db)
