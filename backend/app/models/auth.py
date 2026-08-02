"""ORM model for `revoked_tokens` -- see migration f6b8c0d2e4a5 and
app/core/auth/session_store.py for the durable revocation store this backs."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Index, PrimaryKeyConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RevokedTokenRow(Base):
    __tablename__ = "revoked_tokens"
    __table_args__ = (
        PrimaryKeyConstraint("jti", name="revoked_tokens_pkey"),
        Index("ix_revoked_tokens_expires_at", "expires_at"),
    )

    jti: Mapped[str] = mapped_column(String(64))
    revoked_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
