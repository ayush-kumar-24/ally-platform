"""Dependency injection for the Ally chat endpoint.

All wiring lives in the composition root (app.core.container); this file just
adapts it to a FastAPI dependency. Adding real backends (Redis / Postgres /
pgvector / OpenAI / Claude / Gemini) is a change in the container only -- this
file stays one line.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.v1.ally.orchestrator import OrchestratorService
from app.core.container import container
from app.db.session import get_db


def get_orchestrator_service(db: Session = Depends(get_db)) -> OrchestratorService:
    return container.orchestrator(db)
