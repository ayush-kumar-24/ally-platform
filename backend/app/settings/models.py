"""SQLAlchemy model for founder settings (Part 1).

One row per founder in `founder_settings`. Holds only the settings that had no home
before -- reminder preferences and app-level security preferences. Profile,
account and notifications live in their existing tables/columns and are not
duplicated here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FounderSettings(Base):
    __tablename__ = "founder_settings"

    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    # --- reminder preferences ---
    daily_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    reminder_time: Mapped[str] = mapped_column(String(5), nullable=False, server_default=text("'09:00'"))
    task_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    meeting_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    goal_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # --- app-level security preferences (credentials/2FA are provider-owned) ---
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("60"))
    login_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
