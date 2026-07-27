"""MemoryPolicy -- decides what is remembered, what expires, what is permanent.

Isolated from storage and from the service's orchestration so retention rules can
change (or be A/B'd) in one place without touching persistence or search. Pure and
deterministic: given the same inputs and clock time, the same classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.api.v1.ally.memory.schemas import MemoryItem, MemoryType, Retention

# Types that are inherently durable founder knowledge.
_PERMANENT_TYPES = frozenset({MemoryType.LONG_TERM, MemoryType.STRATEGIC, MemoryType.PREFERENCE})


@dataclass(frozen=True)
class MemoryPolicyConfig:
    min_importance_to_store: int = 1
    permanent_importance_threshold: int = 90
    working_ttl: timedelta = timedelta(days=7)
    session_ttl: timedelta = timedelta(hours=12)


class MemoryPolicy:
    def __init__(self, config: MemoryPolicyConfig | None = None):
        self.config = config or MemoryPolicyConfig()

    def should_remember(self, memory_type: MemoryType, importance: int, content: str) -> bool:
        """Gate: only non-empty, sufficiently-important information is stored."""
        return bool(content and content.strip()) and importance >= self.config.min_importance_to_store

    def classify(
        self, memory_type: MemoryType, importance: int, session_id: int | None, now: datetime
    ) -> tuple[Retention, datetime | None]:
        """Assign retention + expiry:
          * durable types, or anything highly important -> PERMANENT (never expires)
          * SESSION type -> SESSION retention, expires after session_ttl
          * everything else (e.g. WORKING) -> TEMPORARY, expires after working_ttl
        """
        if importance >= self.config.permanent_importance_threshold or memory_type in _PERMANENT_TYPES:
            return Retention.PERMANENT, None
        if memory_type == MemoryType.SESSION:
            return Retention.SESSION, now + self.config.session_ttl
        return Retention.TEMPORARY, now + self.config.working_ttl

    def is_expired(self, item: MemoryItem, now: datetime) -> bool:
        return item.is_expired(now)
