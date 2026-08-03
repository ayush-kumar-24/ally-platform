"""Usage metrics for the admin panel, derived from the daily token meter.

Cost estimation
---------------
`estimated_cost_usd` is exactly that -- an estimate. It multiplies tokens by a
blended rate from the environment, because the real cost depends on which model
served each request and on the prompt/completion split, neither of which the daily
counter records. It is labelled `estimated` everywhere it surfaces so nobody
reconciles a bill against it.

When per-request provider cost is recorded (the `llm_usage` table the dashboard
already looks for), this should read that instead and stop estimating.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

#: Blended USD per 1,000 tokens. Override with ALLY_BLENDED_COST_PER_1K.
DEFAULT_COST_PER_1K_USD = 0.002


def cost_per_1k() -> float:
    try:
        return float(os.environ.get("ALLY_BLENDED_COST_PER_1K", DEFAULT_COST_PER_1K_USD))
    except (TypeError, ValueError):
        return DEFAULT_COST_PER_1K_USD


def estimate_cost_usd(tokens: int) -> float:
    return round((tokens / 1000.0) * cost_per_1k(), 4)


@dataclass(frozen=True)
class UsageSummary:
    """One founder's usage, or the whole system when founder_id is None."""

    founder_id: int | None
    tokens_today: int
    tokens_month: int
    requests_month: int
    avg_tokens_per_request: float
    credits_remaining: int | None
    estimated_cost_today_usd: float
    estimated_cost_month_usd: float
    unbilled_tokens: int = 0
    unbilled_credits: int = 0


class UsageMetricsService:
    """Read-only aggregations. Every query degrades to zero rather than raising:
    a missing table must dim one number, not break the admin dashboard."""

    def __init__(self, db, *, clock=None):
        self.db = db
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def _scalar(self, sql: str, params: dict | None = None, default=0):
        try:
            value = self.db.execute(text(sql), params or {}).scalar()
            return default if value is None else value
        except Exception:
            self.db.rollback()
            return default

    def summary(self, founder_id: int | None = None) -> UsageSummary:
        now = self._now()
        today = now.date()
        month_start = today.replace(day=1)
        scope = "and founder_id = :fid" if founder_id is not None else ""
        p = {"today": today, "month_start": month_start}
        if founder_id is not None:
            p["fid"] = founder_id

        tokens_today = int(self._scalar(
            f"""select coalesce(sum(tokens_used), 0) from daily_token_usage
                 where usage_date = :today {scope}""", p))
        tokens_month = int(self._scalar(
            f"""select coalesce(sum(tokens_used), 0) from daily_token_usage
                 where usage_date >= :month_start {scope}""", p))

        # Requests are counted from the ledger's CONSUME rows -- the daily counter
        # stores totals, not a per-request breakdown.
        req_scope = "and user_id = :fid" if founder_id is not None else ""
        requests_month = int(self._scalar(
            f"""select count(*) from credit_transactions
                 where type = 'consume' and created_at >= :month_start {req_scope}""", p))

        credits_remaining = None
        if founder_id is not None:
            credits_remaining = int(self._scalar(
                "select coalesce(credits_balance, 0) from founders where founder_id = :fid",
                {"fid": founder_id}))

        unbilled_scope = "and founder_id = :fid" if founder_id is not None else ""
        unbilled_tokens = int(self._scalar(
            f"""select coalesce(sum(tokens), 0) from unbilled_usage
                 where resolved = false {unbilled_scope}""", p))
        unbilled_credits = int(self._scalar(
            f"""select coalesce(sum(credits_owed), 0) from unbilled_usage
                 where resolved = false {unbilled_scope}""", p))

        return UsageSummary(
            founder_id=founder_id,
            tokens_today=tokens_today,
            tokens_month=tokens_month,
            requests_month=requests_month,
            avg_tokens_per_request=(round(tokens_month / requests_month, 1)
                                    if requests_month else 0.0),
            credits_remaining=credits_remaining,
            estimated_cost_today_usd=estimate_cost_usd(tokens_today),
            estimated_cost_month_usd=estimate_cost_usd(tokens_month),
            unbilled_tokens=unbilled_tokens,
            unbilled_credits=unbilled_credits,
        )

    def daily_series(self, founder_id: int | None = None, *, days: int = 30) -> list[dict]:
        """Token usage per day, oldest first -- for a sparkline or bar chart."""
        since = self._now().date() - timedelta(days=days - 1)
        scope = "and founder_id = :fid" if founder_id is not None else ""
        p: dict = {"since": since}
        if founder_id is not None:
            p["fid"] = founder_id
        try:
            rows = self.db.execute(text(
                f"""select usage_date, coalesce(sum(tokens_used), 0) as tokens
                      from daily_token_usage
                     where usage_date >= :since {scope}
                     group by usage_date order by usage_date asc"""), p).mappings().all()
        except Exception:
            self.db.rollback()
            return []
        return [{"date": r["usage_date"].isoformat(), "tokens": int(r["tokens"]),
                 "estimated_cost_usd": estimate_cost_usd(int(r["tokens"]))} for r in rows]

    def top_consumers(self, *, limit: int = 10) -> list[dict]:
        """Heaviest users this month -- where cost and abuse both show up first."""
        month_start = self._now().date().replace(day=1)
        try:
            rows = self.db.execute(text(
                """select d.founder_id, coalesce(sum(d.tokens_used), 0) as tokens,
                          f.full_name, f.email, f.plan_type
                     from daily_token_usage d
                     join founders f on f.founder_id = d.founder_id
                    where d.usage_date >= :since
                    group by d.founder_id, f.full_name, f.email, f.plan_type
                    order by tokens desc limit :lim"""),
                {"since": month_start, "lim": limit}).mappings().all()
        except Exception:
            self.db.rollback()
            return []
        return [{"founder_id": r["founder_id"], "full_name": r["full_name"],
                 "email": r["email"], "plan_type": r["plan_type"],
                 "tokens": int(r["tokens"]),
                 "estimated_cost_usd": estimate_cost_usd(int(r["tokens"]))} for r in rows]
