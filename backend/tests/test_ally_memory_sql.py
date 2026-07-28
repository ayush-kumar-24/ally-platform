"""SQL memory adapter -- row<->DTO mapping (pure, no DB) + live read-path smoke.

The write round-trip against Postgres needs a founders row (auth.users FK), which
the environment can't create, so the mapping is asserted directly and the SELECT
path is smoke-tested against the live empty tables.
"""

from datetime import datetime, timezone

from app.api.v1.ally.memory.schemas import (
    MemoryAudit, MemoryEvent, MemoryEventType, MemoryItem, MemoryMetadata,
    MemoryStatus, MemoryType, Retention,
)
from app.api.v1.ally.memory.sql_repository import (
    SqlMemoryEventRepository, SqlMemoryRepository, _apply_item, _row_to_item,
)
from app.models.memory import FounderMemory, FounderMemoryEvent

_T0 = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 7, 27, 11, 0, tzinfo=timezone.utc)


def _item() -> MemoryItem:
    return MemoryItem(
        memory_id="mem:abc123", founder_id=42, memory_type=MemoryType.STRATEGIC,
        content="Wants to reach profitability by Q4", key="goal:profitability",
        metadata=MemoryMetadata(
            retention=Retention.PERMANENT, status=MemoryStatus.ACTIVE, importance=85,
            tags=("goal", "finance"), session_id=7, expires_at=None,
            audit=MemoryAudit(
                created_at=_T0, updated_at=_T1, created_by="onboarding",
                updated_by="diagnosis", access_count=3, accessed_at=_T1, archived_at=None,
            ),
        ),
    )


def test_item_maps_to_row_and_back():
    item = _item()
    row = _apply_item(FounderMemory(memory_id=item.memory_id), item)
    # DTO -> row
    assert row.memory_type == "strategic"
    assert row.retention == "permanent"
    assert row.status == "active"
    assert row.importance == 85
    assert row.tags == ["goal", "finance"]
    assert row.session_id == 7
    assert row.created_by == "onboarding" and row.updated_by == "diagnosis"
    assert row.access_count == 3
    # row -> DTO (round trip is faithful)
    back = _row_to_item(row)
    assert back == item


def test_row_to_item_enum_and_tags_coercion():
    row = FounderMemory(
        memory_id="mem:x", founder_id=1, memory_type="preference", content="c",
        key=None, retention="session", status="archived", importance=10, tags=None,
        session_id=None, expires_at=None, created_at=_T0, updated_at=_T0,
        created_by="a", updated_by="a", access_count=0, accessed_at=None, archived_at=_T1,
    )
    item = _row_to_item(row)
    assert item.memory_type == MemoryType.PREFERENCE
    assert item.metadata.retention == Retention.SESSION
    assert item.metadata.status == MemoryStatus.ARCHIVED
    assert item.metadata.tags == ()          # None -> empty tuple
    assert item.metadata.audit.archived_at == _T1


def test_event_maps_to_row():
    ev = MemoryEvent(
        memory_id="mem:abc123", founder_id=42, event_type=MemoryEventType.UPDATED,
        timestamp=_T1, actor="diagnosis", details={"importance": 85}, correlation_id="req-1",
    )
    repo = SqlMemoryEventRepository.__new__(SqlMemoryEventRepository)
    row = FounderMemoryEvent(
        memory_id=ev.memory_id, founder_id=ev.founder_id, event_type=ev.event_type.value,
        timestamp=ev.timestamp, actor=ev.actor, details=dict(ev.details),
        correlation_id=ev.correlation_id,
    )
    back = repo._row_to_event(row)
    assert back == ev


def test_live_read_path_on_empty_tables():
    """SELECT path executes against the real Postgres tables (returns empty)."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        fid = 999_999_999
        assert SqlMemoryRepository(db).list_for_founder(fid) == ()
        assert SqlMemoryRepository(db).get("mem:does-not-exist") is None
        assert SqlMemoryEventRepository(db).list_for_founder(fid) == ()
    finally:
        db.close()
