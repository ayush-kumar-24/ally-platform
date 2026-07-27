"""MemoryService -- store / retrieve / update / archive / search / summarize.

Orchestrates the repository + policy + clock. It classifies via the policy,
timestamps via the clock, and enforces deterministic, fail-closed behaviour. It
NEVER calls an LLM, retrieves, traverses the graph, builds prompts, routes or
executes providers -- it only manages structured founder memory.

Boundaries (enforced by imports): only the memory package + core.logger. Memory is
keyed by a plain founder_id (int), so it needs no import of M1-M5; the orchestrator
(M7) supplies the founder_id from AllyContext.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.api.v1.ally.memory.clock import Clock, SystemClock
from app.api.v1.ally.memory.errors import InvalidMemoryError
from app.api.v1.ally.memory.policy import MemoryPolicy
from app.api.v1.ally.memory.repository import (
    InMemoryMemoryEventRepository,
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
    compute_memory_id,
)


class MemoryService:
    def __init__(
        self,
        repository: MemoryRepository,
        *,
        policy: MemoryPolicy | None = None,
        clock: Clock | None = None,
        events: MemoryEventRepository | None = None,
    ):
        self.repository = repository
        self.policy = policy or MemoryPolicy()
        self.clock = clock or SystemClock()
        # Append-only event log -> the memory timeline. On by default so history is
        # always captured; inject a shared store to aggregate across services.
        self.events = events or InMemoryMemoryEventRepository()

    def _emit(
        self, item: MemoryItem, event_type: MemoryEventType, actor: str, now,
        correlation_id: str | None = None, **details,
    ) -> None:
        self.events.append(
            MemoryEvent(
                memory_id=item.memory_id, founder_id=item.founder_id,
                event_type=event_type, timestamp=now, actor=actor, details=dict(details),
                correlation_id=correlation_id,
            )
        )

    # --- Write ------------------------------------------------------------

    def store(
        self,
        founder_id: int,
        memory_type: MemoryType,
        content: str,
        *,
        importance: int = 50,
        tags=(),
        key: str | None = None,
        session_id: int | None = None,
        actor: str = "system",
        correlation_id: str | None = None,
    ) -> MemoryItem | None:
        """Create or update a memory (upsert by identity). Returns None when the
        policy decides the information is not worth remembering; raises
        InvalidMemoryError when the input is malformed."""
        self._validate(founder_id, importance, content)
        if not self.policy.should_remember(memory_type, importance, content):
            return None

        now = self.clock.now()
        memory_id = compute_memory_id(founder_id, memory_type, key, content, session_id)
        retention, expires_at = self.policy.classify(memory_type, importance, session_id, now)
        existing = self.repository.get(memory_id)

        if existing is not None:
            # Update in place -> dedup. Carry the creation history forward.
            audit = replace(existing.metadata.audit, updated_at=now, updated_by=actor)
            metadata = MemoryMetadata(
                retention=retention, status=existing.metadata.status, importance=importance,
                tags=tuple(tags), session_id=session_id, expires_at=expires_at, audit=audit,
            )
            item = replace(existing, content=content, key=key, metadata=metadata)
        else:
            audit = MemoryAudit(created_at=now, updated_at=now, created_by=actor, updated_by=actor)
            metadata = MemoryMetadata(
                retention=retention, status=MemoryStatus.ACTIVE, importance=importance,
                tags=tuple(tags), session_id=session_id, expires_at=expires_at, audit=audit,
            )
            item = MemoryItem(memory_id, founder_id, memory_type, content, key, metadata)

        saved = self.repository.save(item)
        event_type = MemoryEventType.UPDATED if existing is not None else MemoryEventType.CREATED
        self._emit(saved, event_type, actor, now, correlation_id=correlation_id, importance=importance)
        return saved

    def update(
        self, memory_id: str, *, content=None, importance=None, tags=None,
        actor: str = "system", correlation_id: str | None = None,
    ) -> MemoryItem | None:
        item = self.repository.get(memory_id)
        if item is None:
            return None
        new_importance = item.metadata.importance if importance is None else importance
        if not (0 <= new_importance <= 100):
            raise InvalidMemoryError(f"importance {new_importance} out of range [0, 100]")
        now = self.clock.now()
        audit = replace(item.metadata.audit, updated_at=now, updated_by=actor)
        metadata = replace(
            item.metadata,
            importance=new_importance,
            tags=item.metadata.tags if tags is None else tuple(tags),
            audit=audit,
        )
        updated = replace(item, content=item.content if content is None else content, metadata=metadata)
        saved = self.repository.save(updated)
        self._emit(saved, MemoryEventType.UPDATED, actor, now, correlation_id=correlation_id)
        return saved

    def archive(
        self, memory_id: str, *, actor: str = "system", correlation_id: str | None = None
    ) -> MemoryItem | None:
        item = self.repository.get(memory_id)
        if item is None:
            return None
        now = self.clock.now()
        audit = replace(item.metadata.audit, archived_at=now, updated_at=now, updated_by=actor)
        metadata = replace(item.metadata, status=MemoryStatus.ARCHIVED, audit=audit)
        saved = self.repository.save(replace(item, metadata=metadata))
        self._emit(saved, MemoryEventType.ARCHIVED, actor, now, correlation_id=correlation_id)
        return saved

    # --- Read -------------------------------------------------------------

    def retrieve(
        self, memory_id: str, *, touch: bool = True, actor: str = "system",
        correlation_id: str | None = None,
    ) -> MemoryItem | None:
        """Fetch by id. Fail-closed: unknown id -> None. When `touch`, records the
        access on the audit trail (accessed_at + access_count) and emits an ACCESSED
        event -- audit/timeline only, never a ranking effect."""
        item = self.repository.get(memory_id)
        if item is None:
            return None
        if not touch:
            return item
        now = self.clock.now()
        audit = replace(item.metadata.audit, accessed_at=now, access_count=item.metadata.audit.access_count + 1)
        touched = self.repository.save(replace(item, metadata=replace(item.metadata, audit=audit)))
        self._emit(touched, MemoryEventType.ACCESSED, actor, now, correlation_id=correlation_id)
        return touched

    def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        """Filtered, deterministically-ordered search. Read-only (never touches the
        audit). Missing/no matches -> empty result, never fabricated."""
        now = self.clock.now()
        candidates = self.repository.list_for_founder(request.founder_id)
        matched = [i for i in candidates if self._matches(i, request, now)]
        ordered = self._ordered(matched)
        total = len(ordered)
        if request.limit is not None:
            ordered = ordered[: max(0, request.limit)]
        return MemorySearchResult(items=tuple(ordered), total_matched=total, request=request)

    def sweep_expired(
        self, founder_id: int, *, actor: str = "system", correlation_id: str | None = None
    ) -> tuple[MemoryItem, ...]:
        """Emit an EXPIRED event for each active memory that has passed its expiry
        and has not already been marked expired. Idempotent: re-running emits
        nothing new. Expiration stays a derived state -- the item is not mutated;
        this only records the timeline transition."""
        now = self.clock.now()
        already = {
            e.memory_id
            for e in self.events.list_for_founder(founder_id)
            if e.event_type == MemoryEventType.EXPIRED
        }
        swept: list[MemoryItem] = []
        for item in self.repository.list_for_founder(founder_id):
            if item.is_active and self.policy.is_expired(item, now) and item.memory_id not in already:
                self._emit(item, MemoryEventType.EXPIRED, actor, now, correlation_id=correlation_id)
                swept.append(item)
        return tuple(swept)

    def timeline(self, memory_id: str) -> tuple[MemoryEvent, ...]:
        """The ordered event history of one memory."""
        return self.events.list_for_memory(memory_id)

    def founder_timeline(self, founder_id: int) -> tuple[MemoryEvent, ...]:
        """The ordered event history across all of a founder's memories."""
        return self.events.list_for_founder(founder_id)

    def summarize(self, founder_id: int) -> MemorySummary:
        now = self.clock.now()
        items = self.repository.list_for_founder(founder_id)
        active = [i for i in items if i.is_active and not self.policy.is_expired(i, now)]
        archived = [i for i in items if i.metadata.status == MemoryStatus.ARCHIVED]
        expired = [i for i in items if i.is_active and self.policy.is_expired(i, now)]

        def contents(memory_type: MemoryType) -> tuple[str, ...]:
            selected = [i for i in active if i.memory_type == memory_type]
            return tuple(i.content for i in self._ordered(selected))

        return MemorySummary(
            founder_id=founder_id,
            total=len(items),
            active=len(active),
            archived=len(archived),
            expired=len(expired),
            counts_by_type=self._count(active, lambda i: i.memory_type.value),
            counts_by_retention=self._count(active, lambda i: i.metadata.retention.value),
            strategic_goals=contents(MemoryType.STRATEGIC),
            preferences=contents(MemoryType.PREFERENCE),
            recurring_challenges=contents(MemoryType.WORKING),
        )

    # --- Helpers ----------------------------------------------------------

    def _validate(self, founder_id: int, importance: int, content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise InvalidMemoryError("memory content must be a non-empty string")
        if not (0 <= importance <= 100):
            raise InvalidMemoryError(f"importance {importance} out of range [0, 100]")

    def _matches(self, item: MemoryItem, r: MemorySearchRequest, now: datetime) -> bool:
        m = item.metadata
        if r.memory_type is not None and item.memory_type != r.memory_type:
            return False
        if not r.include_archived and m.status == MemoryStatus.ARCHIVED:
            return False
        if not r.include_expired and self.policy.is_expired(item, now):
            return False
        if r.session_id is not None and m.session_id != r.session_id:
            return False
        if r.min_importance is not None and m.importance < r.min_importance:
            return False
        if r.tags and not set(r.tags).issubset(set(m.tags)):
            return False
        if r.date_from is not None and m.audit.created_at < r.date_from:
            return False
        if r.date_to is not None and m.audit.created_at > r.date_to:
            return False
        if r.keyword:
            kw = r.keyword.lower()
            if kw not in item.content.lower() and not any(kw in t.lower() for t in m.tags):
                return False
        return True

    def _ordered(self, items) -> list[MemoryItem]:
        # Deterministic: importance desc, then most-recent created_at, then id.
        # access_count / accessed_at are deliberately NOT ranking factors.
        return sorted(
            items,
            key=lambda i: (-i.metadata.importance, -i.metadata.audit.created_at.timestamp(), i.memory_id),
        )

    def _count(self, items, key) -> dict[str, int]:
        counts: dict[str, int] = {}
        for i in items:
            k = key(i)
            counts[k] = counts.get(k, 0) + 1
        return counts


def build_memory_service(
    repository: MemoryRepository,
    *,
    policy: MemoryPolicy | None = None,
    clock: Clock | None = None,
    events: MemoryEventRepository | None = None,
) -> MemoryService:
    return MemoryService(repository, policy=policy, clock=clock, events=events)
