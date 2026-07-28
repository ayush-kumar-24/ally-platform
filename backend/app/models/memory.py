"""Founder Memory persistence tables (hand-modelled, like partitioned.py).

Durable backing for the Ally Founder-Memory layer (`app/api/v1/ally/memory`),
whose repository was previously in-memory only. Two tables:

- `founder_memory`        -- current-state memory items (one row per memory_id).
- `founder_memory_events` -- append-only lifecycle timeline (never updated).

Columns mirror the frozen DTOs in `ally/memory/schemas.py`. Kept out of the
sqlacodegen-generated `schema.py` so that regeneration never clobbers them.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FounderMemory(Base):
    __tablename__ = "founder_memory"
    __table_args__ = (
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"],
            ondelete="CASCADE", name="founder_memory_founder_id_fkey",
        ),
        PrimaryKeyConstraint("memory_id", name="founder_memory_pkey"),
    )

    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str | None] = mapped_column(String(255))
    retention: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    importance: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    session_id: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[object | None] = mapped_column(DateTime(True))
    created_at: Mapped[object] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[object] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    accessed_at: Mapped[object | None] = mapped_column(DateTime(True))
    archived_at: Mapped[object | None] = mapped_column(DateTime(True))


class FounderMemoryEvent(Base):
    __tablename__ = "founder_memory_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"],
            ondelete="CASCADE", name="founder_memory_events_founder_id_fkey",
        ),
        PrimaryKeyConstraint("event_id", name="founder_memory_events_pkey"),
    )

    # Append-only: no FK to founder_memory so the timeline survives item deletion.
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(String(64), nullable=False)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[object] = mapped_column(DateTime(True), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[object] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
