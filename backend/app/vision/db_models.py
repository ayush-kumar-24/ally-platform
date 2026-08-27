"""SQLAlchemy models for Vision.

Named db_models.py to keep the ORM classes distinct from the frozen domain
models (models.py), same convention as every other module here. Production
persistence only; the hermetic test suite uses the in-memory repository.

Two tables, matching the two frozen dataclasses in models.py:
- vision_territories: one row per (founder, territory), composite PK.
- vision_summary: one row per founder (PK is founder_id itself).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VisionTerritoryRow(Base):
    __tablename__ = "vision_territories"

    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        primary_key=True, index=True)
    territory: Mapped[str] = mapped_column(String(20), primary_key=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tag1: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    tag2: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    #: One picture per territory. Nullable with no default, so "no image" is
    #: genuinely absent rather than an empty string that every reader then has
    #: to remember to treat as absent. `image_storage_path` records which
    #: backend holds THIS file ("s3:<key>" / "local:<name>") -- see the
    #: migration and profile/routes.py, where avatars learned that a single URL
    #: column orphans everything uploaded before a storage switch.
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class VisionSummaryRow(Base):
    __tablename__ = "vision_summary"

    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True)
    target: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    current: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    unit: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
