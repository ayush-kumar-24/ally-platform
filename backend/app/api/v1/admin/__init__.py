"""Admin HTTP API (Phase 12) -- transport only. Role-gated operator endpoints over
the AdminService; every endpoint delegates to the service."""

from app.api.v1.admin.router import router

__all__ = ["router"]
