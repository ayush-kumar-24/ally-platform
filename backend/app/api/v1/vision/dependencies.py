"""Vision API dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.vision.service import VisionService


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_vision_service(db: Session = Depends(get_db)) -> VisionService:
    return container.vision_service(db)
