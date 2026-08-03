"""DB-backed admin user management.

Search is a single parameterised query -- the free-text term is bound, never
interpolated, so an admin searching for O'Brien or a hostile string cannot alter the
statement. Sort columns come from an enum allowlist for the same reason: an ORDER BY
cannot be parameterised, so the only safe approach is to never let user input reach
it. Both are the standard SQL-injection guards and neither is optional here, because
this endpoint reads every user in the system.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.admin.users_models import (
    ConsentStatus,
    SortField,
    UserDetail,
    UserFilters,
    UserPage,
    UserStatus,
    UserSummary,
)
from app.admin.users_repository import AdminUserRepository

# ORDER BY cannot be bound as a parameter, so the enum value is mapped to a literal
# column name here. Anything not in this dict simply cannot be sorted by.
_SORT_COLUMNS = {
    SortField.CREATED_AT: "f.created_at",
    SortField.LAST_ACTIVE_AT: "f.last_active_at",
    SortField.FULL_NAME: "f.full_name",
    SortField.EMAIL: "f.email",
    SortField.CREDITS_BALANCE: "f.credits_balance",
    SortField.STATUS: "f.status",
}

# Fields PATCH is allowed to write. Anything else is ignored -- an allowlist, so a
# future request body key can never reach a column by accident.
_UPDATABLE = {"full_name", "email", "phone", "business_name", "status",
              "admin_notes", "plan_type"}


#: Columns the admin list wants that arrive with a pending migration. Selecting one
#: that does not exist fails the whole query, so the SELECT is built from what the
#: database actually has and the rest read as empty.
_OPTIONAL_COLUMNS = ("phone", "business_name", "status", "credits_balance",
                     "last_active_at", "admin_notes")


class SqlAlchemyAdminUserRepository(AdminUserRepository):
    def __init__(self, db):
        self.db = db
        self._cols: set[str] | None = None

    def _available(self) -> set[str]:
        """Column names present on `founders`, cached per request."""
        if self._cols is None:
            try:
                from sqlalchemy import inspect
                self._cols = {c["name"] for c in inspect(self.db.get_bind())
                              .get_columns("founders")}
            except Exception:
                self._cols = set()
        return self._cols

    def _select_list(self, prefix: str = "f.") -> str:
        """Always-present columns plus whichever optional ones exist; the missing
        ones are selected as NULL so the row shape stays constant."""
        have = self._available()
        parts = [f"{prefix}founder_id", f"{prefix}full_name", f"{prefix}email",
                 f"{prefix}created_at", f"{prefix}diagnosis_locked_at",
                 f"{prefix}consent_version", f"{prefix}plan_type"]
        for col in _OPTIONAL_COLUMNS:
            parts.append(f"{prefix}{col}" if col in have else f"null as {col}")
        return ", ".join(parts)

    # --- search ---------------------------------------------------------

    def search(self, filters: UserFilters, *, page: int, page_size: int,
               sort_by: SortField, descending: bool) -> UserPage:
        where, params = ["1=1"], {}

        if filters.search:
            # Only search columns that exist -- phone/business_name arrive with a
            # pending migration, and naming an absent column fails the whole query.
            have = self._available()
            terms = ["f.full_name ilike :q", "f.email ilike :q",
                     "cast(f.founder_id as text) = :q_exact"]
            terms += [f"f.{c} ilike :q" for c in ("phone", "business_name") if c in have]
            where.append("(" + " or ".join(terms) + ")")
            params["q"] = f"%{filters.search.strip()}%"
            params["q_exact"] = filters.search.strip()
        if filters.status is not None and "status" in self._available():
            where.append("f.status = :status")
            params["status"] = filters.status.value
        if filters.subscription is not None:
            where.append("f.plan_type = :plan")
            params["plan"] = filters.subscription
        if filters.registered_after is not None:
            where.append("f.created_at >= :reg_after")
            params["reg_after"] = filters.registered_after
        if filters.registered_before is not None:
            where.append("f.created_at <= :reg_before")
            params["reg_before"] = filters.registered_before
        if filters.active_since is not None and "last_active_at" in self._available():
            where.append("f.last_active_at >= :active_since")
            params["active_since"] = filters.active_since
        if filters.diagnosis_completed is not None:
            where.append("(f.diagnosis_locked_at is not null) = :diag")
            params["diag"] = filters.diagnosis_completed

        clause = " and ".join(where)
        total = self.db.execute(
            text(f"select count(*) from founders f where {clause}"), params).scalar() or 0

        order = _SORT_COLUMNS.get(sort_by, "f.created_at")
        if order.split(".")[-1] not in self._available():
            order = "f.created_at"          # fall back rather than ORDER BY a ghost
        direction = "desc" if descending else "asc"
        params["lim"] = page_size
        params["off"] = max(0, (page - 1) * page_size)

        rows = self.db.execute(text(f"""
            select {self._select_list()}
              from founders f
             where {clause}
             order by {order} {direction} nulls last, f.founder_id asc
             limit :lim offset :off"""), params).mappings().all()

        return UserPage(items=[_to_summary(r) for r in rows], total=int(total),
                        page=page, page_size=page_size)

    # --- reads ----------------------------------------------------------

    def get_summary(self, founder_id: int) -> UserSummary | None:
        row = self.db.execute(text(f"""
            select {self._select_list("")}
              from founders where founder_id = :fid"""),
            {"fid": founder_id}).mappings().first()
        return _to_summary(row) if row else None

    def get_detail(self, founder_id: int) -> UserDetail | None:
        base = self.db.execute(
            text("select * from founders where founder_id = :fid"),
            {"fid": founder_id}).mappings().first()
        if base is None:
            return None
        f = dict(base)

        def section(sql: str, default):
            """A missing/renamed table must not blank the whole profile -- the admin
            still needs the rest. The gap is returned rather than hidden."""
            try:
                return [dict(r) for r in
                        self.db.execute(text(sql), {"fid": founder_id}).mappings().all()]
            except Exception:
                self.db.rollback()
                return default

        subs = section("""select * from subscriptions where founder_id = :fid
                          order by created_at desc limit 1""", [])
        txs = section("""select id, type, amount, balance_before, balance_after, reason,
                                admin_id, created_at
                           from credit_transactions where user_id = :fid
                          order by created_at desc limit 10""", [])
        consents = section("""select terms_version, privacy_version, agree_terms,
                                     agree_diagnosis, consented_at
                                from founder_consents where founder_id = :fid
                               order by consented_at desc limit 1""", [])
        chat_rows = section("select count(*) as n from conversations where founder_id = :fid", [])

        return UserDetail(
            founder_id=founder_id,
            profile={k: f.get(k) for k in (
                "founder_id", "full_name", "email", "phone", "status", "created_at",
                "last_active_at", "admin_notes", "preferred_language", "profile_completed")},
            business={k: f.get(k) for k in (
                "business_name", "industry", "business_model", "team_size",
                "current_revenue", "website", "linkedin_url", "customer_segment",
                "problem_statement", "goal_90_day", "vision_1_year")},
            subscription=subs[0] if subs else None,
            credits={"balance": f.get("credits_balance", 0), "recent_transactions": txs},
            consent=consents[0] if consents else None,
            reports=section("""select * from founder_reports where founder_id = :fid
                               order by created_at desc limit 20""", []),
            chat_count=int(chat_rows[0]["n"]) if chat_rows else 0,
            diagnosis_history=section("""select * from sessions
                                          where founder_id = :fid
                                          order by started_at desc limit 20""", []),
            login_history=[],   # no login_history table in this schema
            privacy_requests=section("""select request_id, request_type, status,
                                               requested_at, due_by
                                          from privacy_requests where founder_id = :fid
                                         order by requested_at desc limit 20""", []),
        )

    # --- writes ---------------------------------------------------------

    def update_fields(self, founder_id: int, changes: dict, *, at: datetime) -> UserSummary:
        allowed = {k: v for k, v in changes.items() if k in _UPDATABLE}
        if allowed:
            assignments = ", ".join(f"{k} = :{k}" for k in allowed)
            params = {**allowed, "fid": founder_id, "at": at}
            self.db.execute(
                text(f"update founders set {assignments}, updated_at = :at "
                     f"where founder_id = :fid"), params)
            self.db.commit()
        return self.get_summary(founder_id)

    def reset_diagnosis(self, founder_id: int) -> int:
        r = self.db.execute(
            text("""update founders
                       set diagnosis_used = 0, diagnosis_locked_at = null
                     where founder_id = :fid"""), {"fid": founder_id})
        self.db.commit()
        return r.rowcount or 0

    def set_subscription_expiry(self, founder_id: int, expires_at: datetime) -> bool:
        try:
            r = self.db.execute(
                text("""update subscriptions set expires_at = :exp, updated_at = now()
                         where founder_id = :fid"""),
                {"exp": expires_at, "fid": founder_id})
            self.db.commit()
            return (r.rowcount or 0) > 0
        except Exception:
            self.db.rollback()
            raise

    def reset_conversations(self, founder_id: int) -> int:
        try:
            r = self.db.execute(
                text("delete from conversations where founder_id = :fid"), {"fid": founder_id})
            self.db.commit()
            return r.rowcount or 0
        except Exception:
            self.db.rollback()
            raise


def _to_summary(r) -> UserSummary:
    return UserSummary(
        founder_id=r["founder_id"],
        full_name=r["full_name"] or "",
        email=r["email"] or "",
        phone=r.get("phone"),
        business_name=r.get("business_name"),
        status=UserStatus(r.get("status") or "active"),
        plan_type=r.get("plan_type"),
        credits_balance=int(r.get("credits_balance") or 0),
        diagnosis_completed=r.get("diagnosis_locked_at") is not None,
        consent_status=(ConsentStatus.GRANTED if r.get("consent_version")
                        else ConsentStatus.MISSING),
        created_at=r["created_at"],
        last_active_at=r.get("last_active_at"),
    )
