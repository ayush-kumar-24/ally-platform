"""Repository layer -- database access lives here, not in routes.

`BaseRepository` provides generic CRUD; concrete repositories add model-specific
queries. Routes depend on a repository, never on raw SQLAlchemy, so query logic
has one home and is testable in isolation.
"""

from app.repositories.base import BaseRepository
from app.repositories.discovery import DiscoveryCallRepository, discovery_call_repository
from app.repositories.founder import FounderRepository, founder_repository
from app.repositories.founder_context import FounderContextRepository, founder_context_repository
from app.repositories.notification import NotificationRepository, notification_repository

__all__ = [
    "BaseRepository",
    "FounderRepository",
    "founder_repository",
    "FounderContextRepository",
    "founder_context_repository",
    "DiscoveryCallRepository",
    "discovery_call_repository",
    "NotificationRepository",
    "notification_repository",
]
