"""Durable record of usage that was delivered but not billed.

Why this exists
---------------
When the model answers but the meter fails, the right user experience is to return
the answer anyway -- the founder already has their reply and the provider tokens are
already spent, so failing their request would punish them for our accounting
problem. But "return the answer" must not mean "forget it happened": that is
revenue quietly evaporating, invisibly, at exactly the moments the system is
already unhealthy.

So the failure is written here instead of being swallowed. Each row is a claim that
`tokens` were delivered to `founder_id` and never charged, with the error that
caused it. A reconciler can replay them later; until then they are at minimum a
countable, alertable number rather than a silence.

Rows are append-only and marked resolved rather than deleted, so "how much usage
went unbilled last week" stays answerable after the backlog is cleared.
"""

from __future__ import annotations

import abc
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

#: Dedicated logger so alerting can key off this name alone.
logger = logging.getLogger("ally.usage.reconciliation")


@dataclass(frozen=True)
class UnbilledUsage:
    id: int
    founder_id: int
    tokens: int
    credits_owed: int
    source: str                  # "chat" | "stream" | ...
    error: str
    created_at: datetime
    resolved: bool = False
    resolved_at: datetime | None = None


class UnbilledUsageRow(Base):
    __tablename__ = "unbilled_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_owed: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="chat")
    error: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class ReconciliationRepository(abc.ABC):
    @abc.abstractmethod
    def record(self, *, founder_id: int, tokens: int, credits_owed: int, source: str,
               error: str, at: datetime) -> UnbilledUsage: ...

    @abc.abstractmethod
    def list_unresolved(self, *, limit: int = 100) -> list[UnbilledUsage]: ...

    @abc.abstractmethod
    def mark_resolved(self, entry_id: int, at: datetime) -> None: ...

    @abc.abstractmethod
    def unresolved_totals(self) -> dict: ...


class InMemoryReconciliationRepository(ReconciliationRepository):
    def __init__(self) -> None:
        self._rows: list[UnbilledUsage] = []
        self._next_id = 1
        self._lock = threading.RLock()

    def record(self, *, founder_id, tokens, credits_owed, source, error, at) -> UnbilledUsage:
        with self._lock:
            entry = UnbilledUsage(id=self._next_id, founder_id=founder_id, tokens=tokens,
                                  credits_owed=credits_owed, source=source, error=error,
                                  created_at=at)
            self._next_id += 1
            self._rows.append(entry)
            return entry

    def list_unresolved(self, *, limit: int = 100) -> list[UnbilledUsage]:
        with self._lock:
            return [r for r in self._rows if not r.resolved][:limit]

    def mark_resolved(self, entry_id: int, at: datetime) -> None:
        with self._lock:
            self._rows = [
                UnbilledUsage(**{**r.__dict__, "resolved": True, "resolved_at": at})
                if r.id == entry_id else r
                for r in self._rows
            ]

    def unresolved_totals(self) -> dict:
        with self._lock:
            pending = [r for r in self._rows if not r.resolved]
        return {"entries": len(pending),
                "tokens": sum(r.tokens for r in pending),
                "credits": sum(r.credits_owed for r in pending)}


class SqlAlchemyReconciliationRepository(ReconciliationRepository):
    def __init__(self, db):
        self.db = db

    def record(self, *, founder_id, tokens, credits_owed, source, error, at) -> UnbilledUsage:
        row = UnbilledUsageRow(founder_id=founder_id, tokens=tokens,
                               credits_owed=credits_owed, source=source,
                               error=error[:2000], created_at=at)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_domain(row)

    def list_unresolved(self, *, limit: int = 100) -> list[UnbilledUsage]:
        rows = (self.db.query(UnbilledUsageRow)
                .filter(UnbilledUsageRow.resolved.is_(False))
                .order_by(UnbilledUsageRow.created_at.asc())
                .limit(limit).all())
        return [_to_domain(r) for r in rows]

    def mark_resolved(self, entry_id: int, at: datetime) -> None:
        row = self.db.get(UnbilledUsageRow, entry_id)
        if row is not None:
            row.resolved, row.resolved_at = True, at
            self.db.commit()

    def unresolved_totals(self) -> dict:
        from sqlalchemy import func as sqlfunc
        row = (self.db.query(
                    sqlfunc.count(UnbilledUsageRow.id),
                    sqlfunc.coalesce(sqlfunc.sum(UnbilledUsageRow.tokens), 0),
                    sqlfunc.coalesce(sqlfunc.sum(UnbilledUsageRow.credits_owed), 0))
               .filter(UnbilledUsageRow.resolved.is_(False)).first())
        return {"entries": int(row[0] or 0), "tokens": int(row[1] or 0),
                "credits": int(row[2] or 0)}


def _to_domain(r: UnbilledUsageRow) -> UnbilledUsage:
    return UnbilledUsage(id=r.id, founder_id=r.founder_id, tokens=r.tokens,
                         credits_owed=r.credits_owed, source=r.source, error=r.error,
                         created_at=r.created_at, resolved=r.resolved,
                         resolved_at=r.resolved_at)


def report_meter_failure(repository: ReconciliationRepository | None, *, founder_id: int,
                         tokens: int, credits_owed: int, source: str, error: Exception,
                         at: datetime | None = None) -> None:
    """Log loudly and persist the shortfall. Never raises.

    This runs on a path where the user's reply already succeeded, so it must not be
    able to turn that success into a failure -- including when the reconciliation
    store is itself unavailable. In that worst case the structured log is the last
    surviving record, which is why it is written first.
    """
    at = at or datetime.now(timezone.utc)
    logger.error(
        "usage_meter_failed",
        extra={"founder_id": founder_id, "tokens": tokens, "credits_owed": credits_owed,
               "source": source, "error": repr(error)},
        exc_info=error,
    )
    if repository is None:
        return
    try:
        repository.record(founder_id=founder_id, tokens=tokens, credits_owed=credits_owed,
                          source=source, error=repr(error), at=at)
    except Exception:                                    # noqa: BLE001
        logger.exception("usage_reconciliation_write_failed",
                         extra={"founder_id": founder_id, "tokens": tokens})


class ReconciliationService:
    """Replays unbilled usage against the credit ledger."""

    def __init__(self, repository: ReconciliationRepository, *, credit_service=None,
                 clock=None):
        self.repository = repository
        self.credits = credit_service
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def pending(self) -> dict:
        return self.repository.unresolved_totals()

    def replay(self, *, limit: int = 100) -> dict:
        """Charge what was missed. Each entry is independent -- one founder's
        failure must not stop the rest of the backlog from clearing."""
        if self.credits is None:
            return {"attempted": 0, "resolved": 0, "failed": 0}

        from app.credits.models import CreditOperation
        entries = self.repository.list_unresolved(limit=limit)
        resolved = failed = 0
        for entry in entries:
            try:
                self.credits.adjust(entry.founder_id, admin_id=0,
                                    operation=CreditOperation.CONSUME,
                                    amount=entry.credits_owed,
                                    reason=f"Reconciled unbilled {entry.source} usage")
                self.repository.mark_resolved(entry.id, self._now())
                resolved += 1
            except Exception:                            # noqa: BLE001
                # Leave it unresolved so the next run retries it.
                failed += 1
        return {"attempted": len(entries), "resolved": resolved, "failed": failed}
