"""Durable (Postgres) adapters for the Founder Memory repositories.

Implements the same `MemoryRepository` / `MemoryEventRepository` seams the service
depends on, backed by the `founder_memory` / `founder_memory_events` tables. Maps
between the frozen DTOs (schemas.py) and the ORM rows (models/memory.py); the
service, policy and clock are unchanged.

Each write commits, because the MemoryService owns no transaction (it holds no
Session). For batching inside a larger unit of work, inject a non-committing
variant instead.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.ally.memory.repository import (
    MemoryEventRepository,
    MemoryRepository,
)
from app.api.v1.ally.memory.schemas import (
    MemoryAudit,
    MemoryEvent,
    MemoryEventType,
    MemoryItem,
    MemoryMetadata,
    MemoryStatus,
    MemoryType,
    Retention,
)
from app.models.memory import FounderMemory, FounderMemoryEvent


def _row_to_item(row: FounderMemory) -> MemoryItem:
    return MemoryItem(
        memory_id=row.memory_id,
        founder_id=row.founder_id,
        memory_type=MemoryType(row.memory_type),
        content=row.content,
        key=row.key,
        metadata=MemoryMetadata(
            retention=Retention(row.retention),
            status=MemoryStatus(row.status),
            importance=row.importance,
            tags=tuple(row.tags or ()),
            session_id=row.session_id,
            expires_at=row.expires_at,
            audit=MemoryAudit(
                created_at=row.created_at,
                updated_at=row.updated_at,
                created_by=row.created_by,
                updated_by=row.updated_by,
                access_count=row.access_count,
                accessed_at=row.accessed_at,
                archived_at=row.archived_at,
            ),
        ),
    )


def _apply_item(row: FounderMemory, item: MemoryItem) -> FounderMemory:
    m, a = item.metadata, item.metadata.audit
    row.founder_id = item.founder_id
    row.memory_type = item.memory_type.value
    row.content = item.content
    row.key = item.key
    row.retention = m.retention.value
    row.status = m.status.value
    row.importance = m.importance
    row.tags = list(m.tags)
    row.session_id = m.session_id
    row.expires_at = m.expires_at
    row.created_at = a.created_at
    row.updated_at = a.updated_at
    row.created_by = a.created_by
    row.updated_by = a.updated_by
    row.access_count = a.access_count
    row.accessed_at = a.accessed_at
    row.archived_at = a.archived_at
    return row


class SqlMemoryRepository(MemoryRepository):
    """Postgres-backed memory item store (upsert by memory_id)."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, item: MemoryItem) -> MemoryItem:
        row = self.db.get(FounderMemory, item.memory_id)
        if row is None:
            row = FounderMemory(memory_id=item.memory_id)
            _apply_item(row, item)
            self.db.add(row)
        else:
            _apply_item(row, item)
        self.db.commit()
        return item

    def get(self, memory_id: str) -> MemoryItem | None:
        row = self.db.get(FounderMemory, memory_id)
        return _row_to_item(row) if row is not None else None

    def list_for_founder(self, founder_id: int) -> tuple[MemoryItem, ...]:
        rows = self.db.execute(
            select(FounderMemory).where(FounderMemory.founder_id == founder_id)
        ).scalars().all()
        return tuple(_row_to_item(r) for r in rows)

    def delete(self, memory_id: str) -> bool:
        row = self.db.get(FounderMemory, memory_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True


class SqlMemoryEventRepository(MemoryEventRepository):
    """Postgres-backed append-only memory event log (the timeline)."""

    def __init__(self, db: Session):
        self.db = db

    def append(self, event: MemoryEvent) -> MemoryEvent:
        self.db.add(
            FounderMemoryEvent(
                memory_id=event.memory_id,
                founder_id=event.founder_id,
                event_type=event.event_type.value,
                timestamp=event.timestamp,
                actor=event.actor,
                details=dict(event.details),
                correlation_id=event.correlation_id,
            )
        )
        self.db.commit()
        return event

    def _row_to_event(self, row: FounderMemoryEvent) -> MemoryEvent:
        return MemoryEvent(
            memory_id=row.memory_id,
            founder_id=row.founder_id,
            event_type=MemoryEventType(row.event_type),
            timestamp=row.timestamp,
            actor=row.actor,
            details=dict(row.details or {}),
            correlation_id=row.correlation_id,
        )

    def list_for_memory(self, memory_id: str) -> tuple[MemoryEvent, ...]:
        rows = self.db.execute(
            select(FounderMemoryEvent)
            .where(FounderMemoryEvent.memory_id == memory_id)
            .order_by(FounderMemoryEvent.event_id)
        ).scalars().all()
        return tuple(self._row_to_event(r) for r in rows)

    def list_for_founder(self, founder_id: int) -> tuple[MemoryEvent, ...]:
        rows = self.db.execute(
            select(FounderMemoryEvent)
            .where(FounderMemoryEvent.founder_id == founder_id)
            .order_by(FounderMemoryEvent.event_id)
        ).scalars().all()
        return tuple(self._row_to_event(r) for r in rows)


def build_db_memory_service(db: Session, *, resilient: bool = True):
    """A MemoryService backed by the durable Postgres repositories.

    The wiring point for an orchestrator: same MemoryService, DB-persisted stores.
    By default the repositories are wrapped so a DB failure DEGRADES (logged) rather
    than breaking the founder's conversation; pass resilient=False for the raw,
    fail-loud repositories (used by the repo tests).
    """
    from app.api.v1.ally.memory.resilient import (
        ResilientMemoryEventRepository, ResilientMemoryRepository,
    )
    from app.api.v1.ally.memory.service import MemoryService

    items = SqlMemoryRepository(db)
    events = SqlMemoryEventRepository(db)
    if resilient:
        items = ResilientMemoryRepository(items, db)
        events = ResilientMemoryEventRepository(events, db)
    return MemoryService(items, events=events)
