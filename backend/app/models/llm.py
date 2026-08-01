"""LLM operations tables: task->model routing and per-call telemetry.

`model_task_routing` is the DB-driven task->model map (same principle as
scoring_rules): which model serves which task is data, changed with an UPDATE, not
a deploy. `llm_call_log` is append-only per-call telemetry (model, tokens, latency,
estimated cost) so token-budget and cost questions can be answered from real data.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ModelTaskRouting(Base):
    """Which provider+model serves a given LLM task. One active row per task."""

    __tablename__ = "model_task_routing"

    task: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(True), server_default=text("now()")
    )


class LLMCallLog(Base):
    """One row per LLM call. Append-only observability -- writing it must never
    break the call it describes. founder/session are plain ids (no FK) so a log
    row never blocks on referential integrity or cleanup."""

    __tablename__ = "llm_call_log"

    call_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok | error
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    founder_id: Mapped[int | None] = mapped_column(Integer, index=True)
    session_id: Mapped[int | None] = mapped_column(Integer, index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(True), server_default=text("now()"), index=True
    )
