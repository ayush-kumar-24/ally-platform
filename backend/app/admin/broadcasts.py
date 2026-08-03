"""Broadcast notifications -- system messages sent to founders without a deploy.

Supersedes the in-memory Phase 12 announcements (which vanished on restart) with a
DB-backed record that adds audience targeting, a schedule window and read tracking.
The Phase 12 endpoints are left alone; this is additive.

Scheduling is evaluated at read time (`starts_at <= now < ends_at`) rather than by a
job that flips `active`. Same reasoning as credit expiry: a window computed on read
is correct whenever anyone looks, and does not depend on a scheduler having run.
"""

from __future__ import annotations

import abc
import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.middleware.error_handler import AppError


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Audience(str, Enum):
    ALL = "all"
    PLAN = "plan"              # everyone on `audience_plan`
    ACTIVE = "active"
    SUSPENDED = "suspended"


class InvalidBroadcastError(AppError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid broadcast: {reason}.", status_code=422)


@dataclass(frozen=True)
class Broadcast:
    broadcast_id: str
    title: str
    body: str
    severity: Severity
    audience: Audience
    created_by: int
    created_at: datetime
    audience_plan: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True

    def is_live(self, now: datetime) -> bool:
        if not self.active:
            return False
        if self.starts_at is not None and now < self.starts_at:
            return False
        if self.ends_at is not None and now >= self.ends_at:
            return False
        return True

    def targets(self, *, plan: str | None, status: str | None) -> bool:
        if self.audience is Audience.ALL:
            return True
        if self.audience is Audience.PLAN:
            return plan is not None and plan == self.audience_plan
        return status == self.audience.value


class BroadcastRow(Base):
    __tablename__ = "broadcasts"

    broadcast_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="info")
    audience: Mapped[str] = mapped_column(String(30), nullable=False, server_default="all")
    audience_plan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class BroadcastReadRow(Base):
    __tablename__ = "broadcast_reads"

    broadcast_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("broadcasts.broadcast_id", ondelete="CASCADE"), primary_key=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class BroadcastRepository(abc.ABC):
    @abc.abstractmethod
    def create(self, broadcast: Broadcast) -> Broadcast: ...

    @abc.abstractmethod
    def list(self, *, include_inactive: bool = False) -> list[Broadcast]: ...

    @abc.abstractmethod
    def get(self, broadcast_id: str) -> Broadcast | None: ...

    @abc.abstractmethod
    def set_active(self, broadcast_id: str, active: bool) -> Broadcast | None: ...

    @abc.abstractmethod
    def mark_read(self, broadcast_id: str, founder_id: int, at: datetime) -> None: ...

    @abc.abstractmethod
    def read_ids(self, founder_id: int) -> set[str]: ...


class InMemoryBroadcastRepository(BroadcastRepository):
    def __init__(self) -> None:
        self._rows: dict[str, Broadcast] = {}
        self._reads: set[tuple[str, int]] = set()
        self._lock = threading.RLock()

    def create(self, broadcast: Broadcast) -> Broadcast:
        with self._lock:
            self._rows[broadcast.broadcast_id] = broadcast
            return broadcast

    def list(self, *, include_inactive: bool = False) -> list[Broadcast]:
        with self._lock:
            rows = sorted(self._rows.values(), key=lambda b: b.created_at, reverse=True)
        return rows if include_inactive else [b for b in rows if b.active]

    def get(self, broadcast_id: str) -> Broadcast | None:
        with self._lock:
            return self._rows.get(broadcast_id)

    def set_active(self, broadcast_id: str, active: bool) -> Broadcast | None:
        with self._lock:
            current = self._rows.get(broadcast_id)
            if current is None:
                return None
            updated = replace(current, active=active)
            self._rows[broadcast_id] = updated
            return updated

    def mark_read(self, broadcast_id: str, founder_id: int, at: datetime) -> None:
        with self._lock:
            self._reads.add((broadcast_id, founder_id))

    def read_ids(self, founder_id: int) -> set[str]:
        with self._lock:
            return {bid for bid, fid in self._reads if fid == founder_id}


class SqlAlchemyBroadcastRepository(BroadcastRepository):
    def __init__(self, db):
        self.db = db

    def create(self, broadcast: Broadcast) -> Broadcast:
        self.db.add(BroadcastRow(
            broadcast_id=broadcast.broadcast_id, title=broadcast.title, body=broadcast.body,
            severity=broadcast.severity.value, audience=broadcast.audience.value,
            audience_plan=broadcast.audience_plan, starts_at=broadcast.starts_at,
            ends_at=broadcast.ends_at, active=broadcast.active,
            created_by=broadcast.created_by, created_at=broadcast.created_at))
        self.db.commit()
        return broadcast

    def list(self, *, include_inactive: bool = False) -> list[Broadcast]:
        q = self.db.query(BroadcastRow)
        if not include_inactive:
            q = q.filter(BroadcastRow.active.is_(True))
        return [_to_domain(r) for r in q.order_by(BroadcastRow.created_at.desc()).all()]

    def get(self, broadcast_id: str) -> Broadcast | None:
        row = self.db.get(BroadcastRow, broadcast_id)
        return _to_domain(row) if row else None

    def set_active(self, broadcast_id: str, active: bool) -> Broadcast | None:
        row = self.db.get(BroadcastRow, broadcast_id)
        if row is None:
            return None
        row.active = active
        self.db.commit()
        self.db.refresh(row)
        return _to_domain(row)

    def mark_read(self, broadcast_id: str, founder_id: int, at: datetime) -> None:
        existing = self.db.get(BroadcastReadRow,
                               {"broadcast_id": broadcast_id, "founder_id": founder_id})
        if existing is None:
            self.db.add(BroadcastReadRow(broadcast_id=broadcast_id,
                                         founder_id=founder_id, read_at=at))
            self.db.commit()

    def read_ids(self, founder_id: int) -> set[str]:
        rows = (self.db.query(BroadcastReadRow.broadcast_id)
                .filter(BroadcastReadRow.founder_id == founder_id).all())
        return {r[0] for r in rows}


def _to_domain(r: BroadcastRow) -> Broadcast:
    return Broadcast(
        broadcast_id=r.broadcast_id, title=r.title, body=r.body,
        severity=Severity(r.severity), audience=Audience(r.audience),
        audience_plan=r.audience_plan, starts_at=r.starts_at, ends_at=r.ends_at,
        active=r.active, created_by=r.created_by, created_at=r.created_at)


MAX_TITLE = 200
MAX_BODY = 5000


class BroadcastService:
    def __init__(self, repository: BroadcastRepository, *, clock=None, id_factory=None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    def create(self, *, admin_id: int, title: str, body: str,
               severity: Severity = Severity.INFO, audience: Audience = Audience.ALL,
               audience_plan: str | None = None, starts_at: datetime | None = None,
               ends_at: datetime | None = None) -> Broadcast:
        title, body = (title or "").strip(), (body or "").strip()
        if not title:
            raise InvalidBroadcastError("a title is required")
        if not body:
            raise InvalidBroadcastError("a body is required")
        if len(title) > MAX_TITLE:
            raise InvalidBroadcastError(f"title may not exceed {MAX_TITLE} characters")
        if len(body) > MAX_BODY:
            raise InvalidBroadcastError(f"body may not exceed {MAX_BODY} characters")
        if audience is Audience.PLAN and not audience_plan:
            raise InvalidBroadcastError("audience 'plan' requires audience_plan")
        if starts_at and ends_at and ends_at <= starts_at:
            raise InvalidBroadcastError("ends_at must be after starts_at")

        return self.repository.create(Broadcast(
            broadcast_id=self._new_id(), title=title, body=body, severity=severity,
            audience=audience, audience_plan=audience_plan, starts_at=starts_at,
            ends_at=ends_at, active=True, created_by=admin_id, created_at=self._now()))

    def list_all(self, *, include_inactive: bool = True) -> list[Broadcast]:
        return self.repository.list(include_inactive=include_inactive)

    def deactivate(self, broadcast_id: str) -> Broadcast | None:
        return self.repository.set_active(broadcast_id, False)

    def for_founder(self, founder_id: int, *, plan: str | None = None,
                    status: str | None = None,
                    include_read: bool = False) -> list[Broadcast]:
        """Live broadcasts targeting this founder."""
        now = self._now()
        seen = set() if include_read else self.repository.read_ids(founder_id)
        return [b for b in self.repository.list(include_inactive=False)
                if b.is_live(now) and b.targets(plan=plan, status=status)
                and b.broadcast_id not in seen]

    def mark_read(self, broadcast_id: str, founder_id: int) -> None:
        self.repository.mark_read(broadcast_id, founder_id, self._now())


def build_broadcast_service(repository: BroadcastRepository | None = None, *,
                            clock=None, id_factory=None) -> BroadcastService:
    return BroadcastService(repository or InMemoryBroadcastRepository(),
                            clock=clock, id_factory=id_factory)
