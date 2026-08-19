"""Read-only feedback access for the admin panel.

founder_feedback was write-only from an admin's perspective: founders could
submit a rating or a note, it landed in the table correctly, and no route
anywhere in the real admin panel (panel_router.py / panel_router_v2.py) ever
read it back. A separate, older `GET /admin/feedback` existed (app/api/v1/
admin/router.py, the Phase 12 scaffold) but was wired to an in-memory stub
seeded with nothing -- live-verified empty even with real rows in the
database. This is the first admin-visible, DB-backed read path for it.

No write path here, same reasoning as ConversationReadRepository: support/
admin can see what founders said, never edit or delete it.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text


@dataclass(frozen=True)
class FeedbackItem:
    feedback_id: int
    founder_id: int
    founder_name: str
    founder_email: str
    feedback_type: str
    rating: int | None
    comment: str | None
    session_id: int | None
    report_id: int | None
    collected_at: datetime


@dataclass(frozen=True)
class FeedbackStats:
    """Aggregate counts, computed over the same filter as the list -- so a
    filtered-to-1-star view and its stats always agree with each other."""

    total: int
    rated_count: int          # how many of `total` actually carry a rating
    average_rating: float | None
    by_type: dict[str, int] = field(default_factory=dict)


class FeedbackReadRepository(abc.ABC):
    @abc.abstractmethod
    def list_feedback(self, *, feedback_type: str | None = None,
                      limit: int = 50, offset: int = 0) -> tuple[list[FeedbackItem], int]: ...

    @abc.abstractmethod
    def stats(self, *, feedback_type: str | None = None) -> FeedbackStats: ...


class InMemoryFeedbackReadRepository(FeedbackReadRepository):
    def __init__(self, items: list[FeedbackItem] | None = None):
        self._rows = list(items or [])
        self._lock = threading.RLock()

    def _filtered(self, feedback_type):
        with self._lock:
            rows = list(self._rows)
        if feedback_type is not None:
            rows = [r for r in rows if r.feedback_type == feedback_type]
        rows.sort(key=lambda r: r.collected_at, reverse=True)
        return rows

    def list_feedback(self, *, feedback_type=None, limit=50, offset=0):
        rows = self._filtered(feedback_type)
        return rows[offset:offset + limit], len(rows)

    def stats(self, *, feedback_type=None):
        rows = self._filtered(feedback_type)
        rated = [r.rating for r in rows if r.rating is not None]
        by_type: dict[str, int] = {}
        for r in rows:
            by_type[r.feedback_type] = by_type.get(r.feedback_type, 0) + 1
        return FeedbackStats(
            total=len(rows), rated_count=len(rated),
            average_rating=(sum(rated) / len(rated)) if rated else None,
            by_type=by_type,
        )


class SqlAlchemyFeedbackReadRepository(FeedbackReadRepository):
    def __init__(self, db):
        self.db = db

    def _rows(self, sql: str, params: dict) -> list[dict]:
        try:
            return [dict(r) for r in self.db.execute(text(sql), params).mappings().all()]
        except Exception:
            self.db.rollback()
            return []

    def list_feedback(self, *, feedback_type=None, limit=50, offset=0):
        total_rows = self._rows(
            """select count(*) as n from founder_feedback
                where cast(:ftype as varchar) is null or feedback_type = cast(:ftype as varchar)""",
            {"ftype": feedback_type})
        total = int(total_rows[0]["n"]) if total_rows else 0
        rows = self._rows("""
            select f.feedback_id, f.founder_id, fo.full_name as founder_name,
                   fo.email as founder_email, f.feedback_type, f.rating,
                   f.outcome_text as comment, f.session_id, f.report_id, f.collected_at
              from founder_feedback f
              join founders fo on fo.founder_id = f.founder_id
             where cast(:ftype as varchar) is null or f.feedback_type = cast(:ftype as varchar)
             order by f.collected_at desc
             limit :lim offset :off""",
            {"ftype": feedback_type, "lim": limit, "off": offset})
        return [FeedbackItem(
            feedback_id=r["feedback_id"], founder_id=r["founder_id"],
            founder_name=r.get("founder_name") or "", founder_email=r.get("founder_email") or "",
            feedback_type=r["feedback_type"], rating=r.get("rating"),
            comment=r.get("comment"), session_id=r.get("session_id"),
            report_id=r.get("report_id"), collected_at=r["collected_at"],
        ) for r in rows], total

    def stats(self, *, feedback_type=None):
        agg = self._rows("""
            select count(*) as total,
                   count(rating) as rated_count,
                   avg(rating) as average_rating
              from founder_feedback
             where cast(:ftype as varchar) is null or feedback_type = cast(:ftype as varchar)""",
            {"ftype": feedback_type})
        by_type_rows = self._rows("""
            select feedback_type, count(*) as n from founder_feedback
             where cast(:ftype as varchar) is null or feedback_type = cast(:ftype as varchar)
             group by feedback_type""",
            {"ftype": feedback_type})
        a = agg[0] if agg else {}
        avg = a.get("average_rating")
        return FeedbackStats(
            total=int(a.get("total") or 0),
            rated_count=int(a.get("rated_count") or 0),
            average_rating=round(float(avg), 2) if avg is not None else None,
            by_type={r["feedback_type"]: int(r["n"]) for r in by_type_rows},
        )
