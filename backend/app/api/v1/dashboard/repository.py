"""Dashboard aggregation queries (read-only, founder-scoped).

Raw SQL because these tables are not ORM-mapped and because a handful of tight
aggregate queries is the right shape for the most-hit endpoint in the product.
Every method is parameterised by founder_id; nothing here recomputes a score or
calls a model. The counts are consolidated into ONE query with scalar subqueries.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

# Band -> gauge fill (visual only; the real score is never exposed to the founder).
BAND_FILL = {"Critical Gap": 22, "Needs Attention": 45, "Developing": 66, "Strong": 86}


class DashboardRepository:
    def session_stats(self, db: Session, fid: int) -> dict:
        row = db.execute(
            text(
                "select count(*) filter (where status='completed') as completed, "
                "count(*) filter (where status='in_progress') as in_progress, "
                "count(*) as total, max(completed_at) as last_completed_at "
                "from sessions where founder_id=:f"
            ),
            {"f": fid},
        ).mappings().first()
        return dict(row) if row else {}

    def counts(self, db: Session, fid: int) -> dict:
        """All the tile counts in ONE query (scalar subqueries)."""
        row = db.execute(
            text(
                "select "
                "(select count(*) from conversations where founder_id=:f) as conversations, "
                "(select count(*) from founder_reports where founder_id=:f and is_active is true) as reports, "
                "(select count(*) from discovery_calls where founder_id=:f and status <> 'cancelled') as calls_booked, "
                "(select count(*) from discovery_calls where founder_id=:f and (status='completed' or completed_at is not null)) as calls_completed, "
                "(select count(*) from daily_actions where founder_id=:f and is_completed is false) as actions_open, "
                "(select count(*) from daily_actions where founder_id=:f and is_completed is true) as actions_completed"
            ),
            {"f": fid},
        ).mappings().first()
        return dict(row) if row else {}

    def upcoming_actions(self, db: Session, fid: int, limit: int = 5) -> list[dict]:
        """Today + overdue, incomplete, ordered overdue-first then priority then due date."""
        rows = db.execute(
            text(
                "select action_id, title, description, priority, due_date, "
                "(due_date is not null and due_date < current_date) as is_overdue "
                "from daily_actions "
                "where founder_id=:f and is_completed is false "
                "and (due_date is null or due_date <= current_date or action_date <= current_date) "
                "order by (due_date is not null and due_date < current_date) desc, "
                "case lower(coalesce(priority,'')) when 'high' then 0 when 'medium' then 1 "
                "when 'low' then 2 else 3 end, "
                "due_date asc nulls last, display_order asc nulls last "
                "limit :n"
            ),
            {"f": fid, "n": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def upcoming_call(self, db: Session, fid: int) -> dict | None:
        row = db.execute(
            text(
                "select call_id, status, scheduled_at, duration_minutes, timezone "
                "from discovery_calls "
                "where founder_id=:f and status <> 'cancelled' and coalesce(status,'') <> 'completed' "
                "and (scheduled_at is null or scheduled_at >= now()) "
                "order by scheduled_at asc nulls last limit 1"
            ),
            {"f": fid},
        ).mappings().first()
        return dict(row) if row else None

    def recent_conversations(self, db: Session, fid: int, limit: int = 5) -> list[dict]:
        rows = db.execute(
            text(
                "select conversation_id, title, conversation_type, message_count, last_message_at "
                "from conversations where founder_id=:f "
                "order by coalesce(last_message_at, created_at) desc limit :n"
            ),
            {"f": fid, "n": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def recent_reports(self, db: Session, fid: int, limit: int = 5) -> list[dict]:
        """Report list -- BAND from the snapshot, never the raw score."""
        rows = db.execute(
            text(
                "select report_id, title, business_dna->>'band' as band, generated_at "
                "from founder_reports where founder_id=:f and is_active is true "
                "order by generated_at desc limit :n"
            ),
            {"f": fid, "n": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def current_stage(self, db: Session, fid: int) -> dict | None:
        """Current stage: the current stage assessment if any, else founders.stage_id.
        confidence_score is deliberately NOT selected (founder-facing)."""
        row = db.execute(
            text(
                "select fs.stage_id, fs.stage_name, fs.onboarding_label "
                "from founders f "
                "left join stage_assessments sa on sa.founder_id=f.founder_id and sa.is_current is true "
                "left join founder_stages fs on fs.stage_id = coalesce(sa.stage_id, f.stage_id) "
                "where f.founder_id=:f"
            ),
            {"f": fid},
        ).mappings().first()
        return dict(row) if row and row.get("stage_id") is not None else None


dashboard_repository = DashboardRepository()
