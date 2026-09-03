"""Dashboard metrics and the per-user timeline.

Both are read-only aggregations over data other modules own.

Honesty about unavailable metrics
--------------------------------
Some cards depend on tables that may not exist or be populated in a given
environment. API cost and latency come from `llm_call_log`, which records the
provider's own per-call cost -- so those figures are real, not estimated. Rather than render a
confident `0`, an unavailable metric is returned as `None` with a reason, and the UI
shows "—". A dashboard that displays ₹0 revenue when it simply cannot see the
payments table is worse than one that admits it does not know: the first gets acted
on, the second gets fixed.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

#: "Online right now" -- how stale a last-seen stamp can be and still count.
#: Matches the write side's own throttle (app/core/auth/dependencies.py,
#: `_LAST_ACTIVE_THROTTLE`), so a founder active this instant is never missed
#: by the read side's window being tighter than the write side's granularity.
LIVE_WINDOW = timedelta(minutes=5)


@dataclass(frozen=True)
class Metric:
    """One dashboard card. `value is None` means 'could not be measured'."""

    key: str
    label: str
    value: float | int | None
    unit: str = ""
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class TimelineEvent:
    at: datetime
    kind: str                  # "account" | "diagnosis" | "report" | "subscription"
    #                            | "credits" | "chat" | "privacy" | "admin"
    title: str
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class InsightsRepository(abc.ABC):
    @abc.abstractmethod
    def metrics(self, now: datetime) -> list[Metric]: ...

    @abc.abstractmethod
    def timeline(self, founder_id: int, *, limit: int = 200) -> list[TimelineEvent]: ...


class InMemoryInsightsRepository(InsightsRepository):
    """Offline double so the hermetic suite can assert shaping without a database."""

    def __init__(self, metrics: list[Metric] | None = None,
                 events: dict[int, list[TimelineEvent]] | None = None):
        self._metrics = metrics or []
        self._events = events or {}

    def metrics(self, now: datetime) -> list[Metric]:
        return list(self._metrics)

    def timeline(self, founder_id: int, *, limit: int = 200) -> list[TimelineEvent]:
        return list(self._events.get(founder_id, []))[:limit]


class SqlAlchemyInsightsRepository(InsightsRepository):
    def __init__(self, db):
        self.db = db

    # --- helpers ---------------------------------------------------------

    def _scalar(self, sql: str, params: dict | None = None):
        """Run a scalar query, returning None if the source is unavailable.

        A missing table is a real possibility across environments; it must degrade
        one card, not blow up the whole dashboard.
        """
        try:
            return self.db.execute(text(sql), params or {}).scalar()
        except Exception:
            self.db.rollback()
            return None

    def _metric(self, key: str, label: str, sql: str, params: dict | None = None,
                unit: str = "") -> Metric:
        value = self._scalar(sql, params)
        if value is None:
            return Metric(key=key, label=label, value=None, unit=unit,
                          unavailable_reason="source table unavailable")
        return Metric(key=key, label=label, value=value, unit=unit)

    def _rows(self, sql: str, params: dict | None = None) -> list[dict]:
        try:
            return [dict(r) for r in
                    self.db.execute(text(sql), params or {}).mappings().all()]
        except Exception:
            self.db.rollback()
            return []

    # --- metrics ---------------------------------------------------------

    def metrics(self, now: datetime) -> list[Metric]:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        p = {"since": day_start}
        return [
            self._metric("total_users", "Total users",
                         "select count(*) from founders"),
            # Admin Panel proposal gap #2 ("no live-user view"): `last_active_at`
            # is now stamped on every request (app/core/auth/dependencies.py,
            # `record_last_active`) -- before that write existed, this query ran
            # fine and always answered 0, which is why the card read as
            # permanently blank rather than as an honest "unavailable".
            self._metric("live_now", "Live now",
                         "select count(*) from founders where last_active_at >= :live_since",
                         {"live_since": now - LIVE_WINDOW}),
            self._metric("active_today", "Active today",
                         "select count(*) from founders where last_active_at >= :since", p),
            self._metric("active_7d", "Active last 7 days",
                         "select count(*) from founders where last_active_at >= :week_since",
                         {"week_since": now - timedelta(days=7)}),
            self._metric("diagnoses_today", "Diagnoses today",
                         "select count(*) from sessions where started_at >= :since", p),
            self._metric("credits_used_today", "Credits used today",
                         """select coalesce(abs(sum(amount)), 0) from credit_transactions
                             where created_at >= :since and amount < 0""", p),
            self._metric("revenue", "Revenue (₹)",
                         """select coalesce(sum(amount_inr), 0) from subscriptions
                             where status = 'active'""", unit="₹"),
            self._metric("api_cost", "API cost today",
                         """select coalesce(sum(estimated_cost_usd), 0) from llm_call_log
                             where created_at >= :since""", p, unit="$"),
            self._metric("active_chats", "Active chats",
                         """select count(*) from conversations
                             where updated_at >= :since""", p),
            self._metric("avg_response_ms", "Avg response time",
                         """select round(avg(latency_ms)) from llm_call_log
                             where created_at >= :since""", p, unit="ms"),
        ]

    # --- timeline --------------------------------------------------------

    def timeline(self, founder_id: int, *, limit: int = 200) -> list[TimelineEvent]:
        """Merge every dated record for one founder into one chronological stream.

        Each source is queried independently and a missing one contributes nothing,
        so the timeline degrades source-by-source instead of failing whole.
        """
        p = {"fid": founder_id}
        events: list[TimelineEvent] = []

        for r in self._rows("select created_at, full_name, email from founders "
                            "where founder_id = :fid", p):
            events.append(TimelineEvent(at=r["created_at"], kind="account",
                                        title="Account created",
                                        detail=r.get("email") or ""))

        for r in self._rows("""select created_at, session_id, status from sessions
                                where founder_id = :fid order by started_at desc limit 50""", p):
            events.append(TimelineEvent(at=r["created_at"], kind="diagnosis",
                                        title="Diagnosis session",
                                        detail=str(r.get("status") or ""),
                                        meta={"session_id": r.get("session_id")}))

        for r in self._rows("""select created_at, report_id, report_type from founder_reports
                                where founder_id = :fid order by created_at desc limit 50""", p):
            events.append(TimelineEvent(at=r["created_at"], kind="report",
                                        title="Report generated",
                                        detail=str(r.get("report_type") or ""),
                                        meta={"report_id": r.get("report_id")}))

        for r in self._rows("""select created_at, plan_type, status from subscriptions
                                where founder_id = :fid order by created_at desc limit 20""", p):
            events.append(TimelineEvent(at=r["created_at"], kind="subscription",
                                        title=f"Subscription {r.get('status') or ''}".strip(),
                                        detail=str(r.get("plan_type") or "")))

        for r in self._rows("""select created_at, type, amount, balance_after, reason
                                 from credit_transactions where user_id = :fid
                                order by created_at desc limit 50""", p):
            sign = "+" if (r.get("amount") or 0) >= 0 else ""
            events.append(TimelineEvent(
                at=r["created_at"], kind="credits",
                title=f"Credits {r.get('type')}: {sign}{r.get('amount')}",
                detail=str(r.get("reason") or ""),
                meta={"balance_after": r.get("balance_after")}))

        for r in self._rows("""select created_at, conversation_id, title from conversations
                                where founder_id = :fid order by created_at desc limit 50""", p):
            events.append(TimelineEvent(at=r["created_at"], kind="chat",
                                        title="Conversation started",
                                        detail=str(r.get("title") or ""),
                                        meta={"conversation_id": r.get("conversation_id")}))

        for r in self._rows("""select requested_at, request_type, status from privacy_requests
                                where founder_id = :fid order by requested_at desc limit 50""", p):
            events.append(TimelineEvent(at=r["requested_at"], kind="privacy",
                                        title=f"Privacy request: {r.get('request_type')}",
                                        detail=str(r.get("status") or "")))

        for r in self._rows("""select timestamp, action, admin_email, reason
                                 from admin_audit_log where target_user_id = :fid
                                order by timestamp desc limit 50""", p):
            events.append(TimelineEvent(at=r["timestamp"], kind="admin",
                                        title=f"Admin action: {r.get('action')}",
                                        detail=str(r.get("admin_email") or ""),
                                        meta={"reason": r.get("reason")}))

        return merge_timeline(events, limit=limit)


def merge_timeline(events: list[TimelineEvent], *, limit: int = 200) -> list[TimelineEvent]:
    """Newest first, tolerating naive/aware timestamp mixtures.

    Postgres columns differ across this schema (some `timestamp`, some `timestamptz`),
    so a plain sort would raise on comparing naive to aware. Naive values are treated
    as UTC, which is what the application writes.
    """
    def key(e: TimelineEvent):
        at = e.at
        if at is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)

    return sorted([e for e in events if e.at is not None], key=key, reverse=True)[:limit]


class InsightsService:
    def __init__(self, repository: InsightsRepository, *, clock=None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def dashboard_metrics(self) -> list[Metric]:
        return self.repository.metrics(self._now())

    def user_timeline(self, founder_id: int, *, limit: int = 200) -> list[TimelineEvent]:
        return self.repository.timeline(founder_id, limit=limit)


def build_insights_service(repository: InsightsRepository | None = None, *,
                           clock=None) -> InsightsService:
    return InsightsService(repository or InMemoryInsightsRepository(), clock=clock)
