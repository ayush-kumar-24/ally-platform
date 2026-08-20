"""Framework Usage -- what's real about a founder's relationship to each
framework in their thinking toolkit: whether they've opened it, when, and
any note they wrote.

Public surface (import from here, not from submodules):

    FrameworkUsage              frozen domain DTO
    FrameworkUsageService       business rules; build_framework_usage_service() to construct
    FrameworkUsageRepository    persistence seam (InMemory / SqlAlchemy)
    errors                      FrameworkUsageError and friends -> precise HTTP statuses

Backs the Frameworks page and detail page (frontend/src/pages/
FrameworksPage.jsx, FrameworkDetail.jsx). The framework content itself
stays static on the frontend -- see models.py's docstring.
"""

from app.framework_usage.errors import FrameworkUsageError, InvalidFrameworkUsageInputError
from app.framework_usage.models import FrameworkUsage
from app.framework_usage.repository import FrameworkUsageRepository, InMemoryFrameworkUsageRepository
from app.framework_usage.service import FrameworkUsageService, build_framework_usage_service

__all__ = [
    "FrameworkUsage",
    "FrameworkUsageError",
    "FrameworkUsageRepository",
    "FrameworkUsageService",
    "InMemoryFrameworkUsageRepository",
    "InvalidFrameworkUsageInputError",
    "build_framework_usage_service",
]
