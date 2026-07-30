"""FastAPI dependency for the new settings-preferences endpoints.

Pulls the SettingsService from the container (production DB-backed). Tests override
this with an in-memory-backed service.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.container import container
from app.db.session import get_db
from app.settings.service import SettingsService


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return container.settings_service(db)
