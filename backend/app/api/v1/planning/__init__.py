"""Planning HTTP API -- transport only over the PlanningService."""

from app.api.v1.planning.router import router

__all__ = ["router"]
