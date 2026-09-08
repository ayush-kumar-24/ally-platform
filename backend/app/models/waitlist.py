"""ORM model for `waitlist_registrations` -- see migration b8e3d5a91c47 for the
table, its RLS shape, and why a rejection is a state rather than a delete."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"

#: Every state a registration can be in. Kept next to the model rather than in
#: enums.py because nothing outside the waitlist has an opinion about them.
STATUSES = (PENDING, APPROVED, REJECTED)


class WaitlistRegistration(Base):
    __tablename__ = "waitlist_registrations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="waitlist_registrations_status_check",
        ),
        Index("waitlist_registrations_email_key", "email", unique=True),
        Index("idx_waitlist_status_created", "status", "created_at"),
    )

    registration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Always lower-cased before write -- see services/waitlist.py::normalise_email.
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)

    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()")
    )

    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(True), nullable=True)
    decided_by_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The Supabase auth.users id minted at approval. NULL on an approved row
    #: means the decision was recorded but the identity call did not land --
    #: that founder cannot log in yet, and the panel says so rather than
    #: showing a green tick.
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    access_granted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(True), nullable=True
    )
    approval_email_sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(True), nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def can_sign_in(self) -> bool:
        """Approved AND holding an identity. The two are separate facts: see
        auth_user_id. This is the only honest answer to "are they in?"."""
        return self.status == APPROVED and self.auth_user_id is not None
