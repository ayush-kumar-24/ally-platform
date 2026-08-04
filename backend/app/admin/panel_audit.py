"""Admin Panel audit trail -- immutable, persistent.

Separate from the Phase 12 `audit.py` (which stays as-is) because this records a
richer event: the target user, the old and new values, and the caller's IP. Those
are what turn "an admin changed something" into evidence you can act on.

Immutable by construction: the interface has `record` and reads only. No update, no
delete -- not even for the service that owns it. Storage is the DB (the Phase 12
audit was in-memory, so a restart erased it; that is not an audit trail).
"""

from __future__ import annotations

import abc
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


@dataclass(frozen=True)
class PanelAuditEvent:
    event_id: str
    admin_id: int
    admin_email: str
    admin_role: str
    action: str                     # e.g. "credits.adjust", "user.suspend"
    resource: str                   # e.g. "founder:42"
    timestamp: datetime
    target_user_id: int | None = None
    old_value: str | None = None
    new_value: str | None = None
    ip_address: str | None = None
    result: str = "success"         # "success" | "failure"
    reason: str | None = None


class PanelAuditRow(Base):
    __tablename__ = "admin_audit_log"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    admin_email: Mapped[str] = mapped_column(String(200), nullable=False)
    admin_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource: Mapped[str] = mapped_column(String(120), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, server_default="success")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


def serialise(value: Any) -> str | None:
    """Render an old/new value for storage. Kept in one place so the log format
    stays consistent across every call site."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


class PanelAuditRepository(abc.ABC):
    @abc.abstractmethod
    def record(self, event: PanelAuditEvent) -> PanelAuditEvent:
        """Append. There is deliberately no update or delete."""

    @abc.abstractmethod
    def list(self, *, limit: int = 100, offset: int = 0,
             admin_id: int | None = None,
             target_user_id: int | None = None,
             action: str | None = None) -> tuple[list[PanelAuditEvent], int]:
        """Newest first. Returns (page, total)."""


class InMemoryPanelAuditRepository(PanelAuditRepository):
    def __init__(self) -> None:
        self._events: list[PanelAuditEvent] = []
        self._lock = threading.RLock()

    def record(self, event: PanelAuditEvent) -> PanelAuditEvent:
        with self._lock:
            self._events.append(event)
            return event

    def list(self, *, limit: int = 100, offset: int = 0, admin_id: int | None = None,
             target_user_id: int | None = None, action: str | None = None
             ) -> tuple[list[PanelAuditEvent], int]:
        with self._lock:
            rows = list(reversed(self._events))
        if admin_id is not None:
            rows = [e for e in rows if e.admin_id == admin_id]
        if target_user_id is not None:
            rows = [e for e in rows if e.target_user_id == target_user_id]
        if action:
            rows = [e for e in rows if e.action == action]
        return rows[offset:offset + limit], len(rows)


class SqlAlchemyPanelAuditRepository(PanelAuditRepository):
    def __init__(self, db):
        self.db = db

    def record(self, event: PanelAuditEvent) -> PanelAuditEvent:
        self.db.add(PanelAuditRow(
            event_id=event.event_id, admin_id=event.admin_id, admin_email=event.admin_email,
            admin_role=event.admin_role, action=event.action, resource=event.resource,
            target_user_id=event.target_user_id, old_value=event.old_value,
            new_value=event.new_value, ip_address=event.ip_address, result=event.result,
            reason=event.reason, timestamp=event.timestamp))
        self.db.commit()
        return event

    def list(self, *, limit: int = 100, offset: int = 0, admin_id: int | None = None,
             target_user_id: int | None = None, action: str | None = None
             ) -> tuple[list[PanelAuditEvent], int]:
        # The audit table arrives with a pending migration. Until then an empty
        # trail is the truthful answer -- and far better than 500-ing the page an
        # admin opens to find out what happened. Writes are NOT softened: a failed
        # audit write must still fail its action.
        try:
            return self._list(limit=limit, offset=offset, admin_id=admin_id,
                              target_user_id=target_user_id, action=action)
        except Exception:
            self.db.rollback()
            return [], 0

    def _list(self, *, limit, offset, admin_id, target_user_id, action):
        q = self.db.query(PanelAuditRow)
        if admin_id is not None:
            q = q.filter(PanelAuditRow.admin_id == admin_id)
        if target_user_id is not None:
            q = q.filter(PanelAuditRow.target_user_id == target_user_id)
        if action:
            q = q.filter(PanelAuditRow.action == action)
        total = q.count()
        rows = (q.order_by(PanelAuditRow.timestamp.desc(), PanelAuditRow.event_id.desc())
                 .limit(limit).offset(offset).all())
        return [_to_event(r) for r in rows], total


def _to_event(r: PanelAuditRow) -> PanelAuditEvent:
    return PanelAuditEvent(
        event_id=r.event_id, admin_id=r.admin_id, admin_email=r.admin_email,
        admin_role=r.admin_role, action=r.action, resource=r.resource,
        target_user_id=r.target_user_id, old_value=r.old_value, new_value=r.new_value,
        ip_address=r.ip_address, result=r.result, reason=r.reason, timestamp=r.timestamp)


class AuditRecorder:
    """Convenience wrapper so call sites are one readable line.

    Deliberately swallows nothing: if the audit write fails, the caller's action
    fails too. An action that silently completes without its audit record is worse
    than an action that fails loudly.
    """

    def __init__(self, repository: PanelAuditRepository, *, clock=None, id_factory=None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    def record(self, *, admin, action: str, resource: str, target_user_id: int | None = None,
               old_value: Any = None, new_value: Any = None, ip_address: str | None = None,
               result: str = "success", reason: str | None = None) -> PanelAuditEvent:
        return self.repository.record(PanelAuditEvent(
            event_id=self._new_id(),
            admin_id=getattr(admin, "admin_id", 0),
            admin_email=getattr(admin, "email", ""),
            admin_role=str(getattr(getattr(admin, "role", ""), "value", getattr(admin, "role", ""))),
            action=action, resource=resource, target_user_id=target_user_id,
            old_value=serialise(old_value), new_value=serialise(new_value),
            ip_address=ip_address, result=result, reason=reason, timestamp=self._now()))
