"""Typed DTOs for the Founder Memory Layer (Phase 5, Milestone 6).

Structured founder memory -- NOT chat history. Every item separates three things:
its CONTENT (what is remembered), its METADATA (classification + lifecycle), and
its AUDIT trail (immutable operational history: who/when/how often). The audit is
observational only -- it is never a ranking signal.

All frozen/immutable: an "update" produces a new item + a new audit snapshot; the
prior audit values (created_at, created_by, access_count) are carried forward, so
lifecycle history is never silently mutated.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class MemoryType(str, Enum):
    WORKING = "working"
    LONG_TERM = "long_term"
    SESSION = "session"
    STRATEGIC = "strategic"
    PREFERENCE = "preference"


class Retention(str, Enum):
    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    SESSION = "session"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class MemoryAudit:
    """Immutable lifecycle history. Distinct from the memory content; used for
    explaining why a memory exists, pruning, analytics, debugging and compliance.
    It NEVER affects retrieval ordering or relevance."""

    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    access_count: int = 0
    accessed_at: datetime | None = None
    archived_at: datetime | None = None


@dataclass(frozen=True)
class MemoryMetadata:
    """Classification + lifecycle of a memory (its non-content attributes)."""

    retention: Retention
    status: MemoryStatus
    importance: int                       # 0..100
    tags: tuple[str, ...]
    session_id: int | None
    expires_at: datetime | None           # None = never expires (permanent)
    audit: MemoryAudit


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    founder_id: int
    memory_type: MemoryType
    content: str
    key: str | None
    metadata: MemoryMetadata

    def is_expired(self, now: datetime) -> bool:
        exp = self.metadata.expires_at
        return exp is not None and exp <= now

    @property
    def is_active(self) -> bool:
        return self.metadata.status == MemoryStatus.ACTIVE


@dataclass(frozen=True)
class MemorySearchRequest:
    founder_id: int
    memory_type: MemoryType | None = None
    tags: tuple[str, ...] = ()
    min_importance: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    keyword: str | None = None
    session_id: int | None = None
    include_archived: bool = False
    include_expired: bool = False
    limit: int | None = None


@dataclass(frozen=True)
class MemorySearchResult:
    items: tuple[MemoryItem, ...]
    total_matched: int
    request: MemorySearchRequest

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


class MemoryEventType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    ACCESSED = "accessed"
    ARCHIVED = "archived"
    EXPIRED = "expired"


@dataclass(frozen=True)
class MemoryEvent:
    """An immutable domain event in a memory's life. Appended (never mutated), so
    the ordered sequence of events for a memory (or a founder) is a full timeline,
    complementing the current-state MemoryItem. `details` optionally records what
    changed (e.g. new importance)."""

    memory_id: str
    founder_id: int
    event_type: MemoryEventType
    timestamp: datetime
    actor: str
    details: Mapping[str, Any] = field(default_factory=dict)
    # Caller-supplied request/interaction id (e.g. the orchestrator's request UUID),
    # so every event from one AI interaction can be correlated across layers when
    # inspecting logs. Observational only -- never influences business logic. Not
    # generated here (that would be non-deterministic); the orchestrator passes it.
    correlation_id: str | None = None


@dataclass(frozen=True)
class MemorySummary:
    founder_id: int
    total: int
    active: int
    archived: int
    expired: int
    counts_by_type: Mapping[str, int]
    counts_by_retention: Mapping[str, int]
    strategic_goals: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    recurring_challenges: tuple[str, ...] = ()


def compute_memory_id(
    founder_id: int,
    memory_type: MemoryType,
    key: str | None,
    content: str,
    session_id: int | None = None,
) -> str:
    """Deterministic identity. Same founder + type + session + key (or normalised
    content) -> same id, which is what dedupes/updates rather than duplicating, and
    what keeps session memories isolated (session_id is part of the identity)."""
    basis = key if key else " ".join(content.lower().split())
    raw = f"{founder_id}|{memory_type.value}|{session_id}|{basis}"
    return "mem:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
