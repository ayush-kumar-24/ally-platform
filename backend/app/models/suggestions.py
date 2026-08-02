"""ORM models for `suggestions` / `suggestion_feedback` -- see migration
e5a7b9c1d3f4. Both use the domain's own string ids as their primary key; no
integer-PK/external_id indirection is needed since these tables are new (unlike
conversations/file_uploads, which already existed under an integer PK)."""

from __future__ import annotations

import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SuggestionRow(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        PrimaryKeyConstraint("suggestion_id", name="suggestions_pkey"),
        ForeignKeyConstraint(
            ["conversation_id"], ["conversations.external_id"],
            ondelete="CASCADE", name="suggestions_conversation_id_fkey",
        ),
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"],
            ondelete="CASCADE", name="suggestions_founder_id_fkey",
        ),
        CheckConstraint(
            "suggestion_type IN ('follow_up','clarification','missing_information',"
            "'summarization','attachment_review','link_discussion','continue_conversation',"
            "'goal_reminder')",
            name="suggestions_type_check",
        ),
        CheckConstraint("priority IN ('low','medium','high','critical')", name="suggestions_priority_check"),
        CheckConstraint(
            "source IN ('conversation','ai_response','attachment','link','context','system')",
            name="suggestions_source_check",
        ),
        CheckConstraint("status IN ('active','archived','deleted')", name="suggestions_status_check"),
        CheckConstraint(
            "feedback IN ('pending','accepted','dismissed','ignored')", name="suggestions_feedback_check"
        ),
        Index("ix_suggestions_conversation_id", "conversation_id"),
        Index("ix_suggestions_founder_id", "founder_id"),
    )

    suggestion_id: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    suggestion_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_description: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    feedback: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    relevance_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, server_default=text("0"))
    rank: Mapped[int | None] = mapped_column(Integer)
    meta_data: Mapped[dict] = mapped_column("meta_data", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class SuggestionFeedbackRow(Base):
    __tablename__ = "suggestion_feedback"
    __table_args__ = (
        PrimaryKeyConstraint("feedback_id", name="suggestion_feedback_pkey"),
        ForeignKeyConstraint(
            ["suggestion_id"], ["suggestions.suggestion_id"],
            ondelete="CASCADE", name="suggestion_feedback_suggestion_id_fkey",
        ),
        ForeignKeyConstraint(
            ["founder_id"], ["founders.founder_id"],
            ondelete="CASCADE", name="suggestion_feedback_founder_id_fkey",
        ),
        CheckConstraint(
            "feedback_type IN ('pending','accepted','dismissed','ignored')",
            name="suggestion_feedback_type_check",
        ),
        Index("ix_suggestion_feedback_suggestion_id", "suggestion_id"),
    )

    feedback_id: Mapped[str] = mapped_column(String(64))
    suggestion_id: Mapped[str] = mapped_column(String(64), nullable=False)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    note: Mapped[str | None] = mapped_column(Text)
