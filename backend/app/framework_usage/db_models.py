"""SQLAlchemy model for framework usage.

Named db_models.py to keep the ORM class distinct from the frozen domain
model (models.py), same convention as every other module here. Production
persistence only; the hermetic test suite uses the in-memory repository.

framework_id is a plain string column, not a foreign key -- see models.py's
docstring for why this table deliberately doesn't know about
data/frameworks.js's list.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FrameworkUsageRow(Base):
    __tablename__ = "framework_usage"

    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        primary_key=True, index=True)
    framework_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
