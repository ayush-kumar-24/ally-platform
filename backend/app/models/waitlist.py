"""ORM model for `waitlist_registrations` -- see migration b8e3d5a91c47 for the
table, its RLS shape, and why a rejection is a state rather than a delete."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, text
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


class WaitlistSlotOpening(Base):
    """One act of opening slots -- see migration a4d7c6e2b915.

    The effective cap is `WAITLIST_APPROVAL_CAP` plus the sum of `slots_opened`
    here, so the environment value stays the starting size of the list and the
    panel adds to it. Append-only: two admins opening slots at the same moment
    insert two rows rather than racing on one counter.
    """

    __tablename__ = "waitlist_slot_openings"
    __table_args__ = (
        CheckConstraint("slots_opened > 0", name="waitlist_slot_openings_positive"),
        CheckConstraint("approved_count >= 0", name="waitlist_slot_openings_approved_nonneg"),
    )

    opening_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slots_opened: Mapped[int] = mapped_column(Integer, nullable=False)

    #: How many of those slots actually became approvals. Lower than
    #: slots_opened when the queue was shorter than the number opened, or when
    #: an identity call failed; the unused capacity stays available.
    approved_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    opened_by_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()")
    )


class DirectSignupCapacity(Base):
    """The singleton counter gating direct sign-in -- see migration
    c8f3a92e1d47 for the full reasoning.

    Exactly one row (`id` is a boolean CHECKed to always be true). `remaining`
    is how many strangers may still sign in and get a founders row with no
    queue and no admin approval; it is decremented inside the same
    transaction as the founders row it gates (see services/provisioning.py)
    so two concurrent sign-ins for the last slot cannot both succeed.
    """

    __tablename__ = "direct_signup_capacity"
    __table_args__ = (
        CheckConstraint("id", name="direct_signup_capacity_singleton"),
        CheckConstraint("remaining >= 0", name="direct_signup_capacity_nonneg"),
    )

    id: Mapped[bool] = mapped_column(Boolean, primary_key=True, default=True)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()")
    )
