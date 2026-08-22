"""ORM model for per-founder calendar connections.

One row per (founder, provider). See the e2b5c8d47f63 migration for why this is
separate from the discovery-booking service account, and why `provider` is a
plain column rather than an enum.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

# Connection lifecycle. `error` and `revoked` are deliberately distinct: a
# refresh that failed once is not evidence the founder withdrew access, and
# telling them to reconnect over a transient Google outage teaches them to
# ignore the message that matters.
STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
STATUS_ERROR = "error"

PROVIDER_GOOGLE = "google"


class CalendarConnectionRow(Base):
    __tablename__ = "calendar_connections"
    __table_args__ = (
        UniqueConstraint("founder_id", "provider",
                         name="uq_calendar_connection_founder_provider"),
    )

    connection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False,
                                          server_default=PROVIDER_GOOGLE)
    account_email: Mapped[str] = mapped_column(String(320), nullable=False, server_default="")
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=STATUS_ACTIVE)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
