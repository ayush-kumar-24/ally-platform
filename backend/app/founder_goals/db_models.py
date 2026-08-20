"""SQLAlchemy model for founder goals.

Named db_models.py to keep the ORM class distinct from the frozen domain
model (models.py), same convention as every other module here. Production
persistence only; the hermetic test suite uses the in-memory repository.

Table name is `founder_goals`, not `goals` -- app.planning already owns a
`planning_goals` table for a different, nested concept (see models.py's
docstring). Distinct names keep the two from ever being confused in a
migration, a query, or an admin dashboard.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FounderGoalRow(Base):
    __tablename__ = "founder_goals"

    goal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
