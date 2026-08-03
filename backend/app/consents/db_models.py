"""SQLAlchemy model for the consent ledger.

Named db_models.py to keep the ORM class distinct from the frozen domain model.
Production persistence only; the hermetic test suite uses the in-memory repository.

Append-only by construction: rows are only ever INSERTed (see db_repository), and
there is no updated_at column because a record is never modified after it is written.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ConsentRow(Base):
    __tablename__ = "founder_consents"

    consent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        nullable=False, index=True)
    terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    agree_terms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    agree_diagnosis: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
