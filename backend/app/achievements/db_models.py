"""SQLAlchemy model for founder achievements.

Named db_models.py to keep the ORM class distinct from the frozen domain
model (models.py), same convention as every other module here. Production
persistence only; the hermetic test suite uses the in-memory repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AchievementRow(Base):
    __tablename__ = "achievements"

    achievement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, server_default="")
    occurred_on: Mapped[str] = mapped_column(String(50), nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
