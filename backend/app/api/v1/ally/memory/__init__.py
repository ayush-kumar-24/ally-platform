"""Ally Founder Memory Layer (Phase 5, Milestone 6).

Deterministic, offline structured founder memory (NOT chat history). Classifies and
persists founder knowledge across sessions with an immutable audit trail, and
supports store/retrieve/update/archive/search/summarize. It never calls an LLM,
retrieves, traverses the graph, builds prompts, routes or executes -- and it fails
closed to an empty result, never fabricating a memory.
"""

from app.api.v1.ally.memory.clock import Clock, SystemClock
from app.api.v1.ally.memory.errors import InvalidMemoryError, MemoryError
from app.api.v1.ally.memory.policy import MemoryPolicy, MemoryPolicyConfig
from app.api.v1.ally.memory.repository import (
    InMemoryMemoryEventRepository,
    InMemoryMemoryRepository,
    MemoryEventRepository,
    MemoryRepository,
)
from app.api.v1.ally.memory.schemas import (
    MemoryAudit,
    MemoryEvent,
    MemoryEventType,
    MemoryItem,
    MemoryMetadata,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryStatus,
    MemorySummary,
    MemoryType,
    Retention,
    compute_memory_id,
)
from app.api.v1.ally.memory.service import MemoryService, build_memory_service

__all__ = [
    "MemoryService",
    "build_memory_service",
    "MemoryRepository",
    "InMemoryMemoryRepository",
    "MemoryEventRepository",
    "InMemoryMemoryEventRepository",
    "MemoryPolicy",
    "MemoryPolicyConfig",
    "Clock",
    "SystemClock",
    "MemoryItem",
    "MemoryMetadata",
    "MemoryAudit",
    "MemorySearchRequest",
    "MemorySearchResult",
    "MemorySummary",
    "MemoryEvent",
    "MemoryEventType",
    "MemoryType",
    "Retention",
    "MemoryStatus",
    "compute_memory_id",
    "MemoryError",
    "InvalidMemoryError",
]
