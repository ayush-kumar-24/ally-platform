"""Partitioned tables: messages, analytics_events, audit_logs.

sqlacodegen skips PostgreSQL partitioned parents, so these three are modelled by
hand from the live schema. Two deliberate choices:

- Each has NO primary key in the database (a partitioned append log). SQLAlchemy
  requires a PK to map a class, so the id column is marked primary_key=True at the
  ORM level only. Alembic autogenerate does not diff primary keys, so this does
  not create migration drift.
- Indexes are intentionally omitted -- the alembic env.py guard ignores any index
  that exists in the database but not in a model, so leaving them out keeps the
  models lean without provoking a drop.

Columns, foreign keys, and ON DELETE behaviour mirror the database exactly.
"""

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id"], ["conversations.conversation_id"],
            ondelete="CASCADE", name="messages_conversation_id_fkey1",
        ),
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"], name="messages_founder_id_fkey1",
        ),
    )

    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'text'::character varying"))
    # 'metadata' is reserved on a declarative class -- map the column under a safe name.
    meta_data: Mapped[dict | None] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    is_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    edited_at: Mapped[object | None] = mapped_column(DateTime(True))
    created_at: Mapped[object] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"],
            ondelete="SET NULL", name="analytics_events_founder_id_fkey1",
        ),
    )

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    founder_id: Mapped[int | None] = mapped_column(Integer)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_category: Mapped[str] = mapped_column(String(50), nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    session_id: Mapped[str | None] = mapped_column(String(100))
    device_type: Mapped[str | None] = mapped_column(String(20))
    platform: Mapped[str | None] = mapped_column(String(20))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[object] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"],
            ondelete="SET NULL", name="audit_logs_founder_id_fkey1",
        ),
    )

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    founder_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    action_details: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    browser: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
