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
    CookieStatus,
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


#: The founder's diagnosis, in delete order. Children first; `sessions` last,
#: because deleting it cascades to `answers`, `detected_root_causes`,
#: `founder_reports` and `internal_intelligence_reports` -- naming those
#: explicitly first is what makes the returned row count mean something, and
#: what keeps this readable as "everything a diagnosis leaves behind".
#:
#: Three of these are keyed to the FOUNDER, not to the session, so deleting
#: `sessions` alone would leave them behind: `founder_dna_answers` (the Founder
#: DNA phase), `current_problem_answers` (the Current Problem phase) and
#: `stage_assessments`. And `report_shares` has no foreign key to
#: `founder_reports` at all, so its rows would survive pointing at reports that
#: no longer exist -- live share links to a deleted report.
_DIAGNOSIS_TABLES: tuple[str, ...] = (
    "report_shares",
    "internal_intelligence_reports",
    "founder_reports",
    "detected_root_causes",
    "answers",
    "stage_assessments",
    "founder_dna_answers",
    "current_problem_answers",
    "rag_retrieval_log",
    "sessions",
)

#: Every `founders` column the guided onboarding writes, derived from the four
#: section maps in frontend/src/services/profile.js (BUSINESS, FOUNDER, GOALS,
#: PROFILE) -- the only things that write them.
#:
#: `full_name` and `email` are deliberately absent. Onboarding's first question
#: pre-fills the name and lets a founder change it, but the column is NOT NULL
#: and comes from signup rather than from onboarding; clearing it would break
#: the row and take away an identity the founder never offered to give up.
_ONBOARDING_COLUMNS: tuple[str, ...] = (
    "stage_id", "experience_level", "current_revenue",
    "building_summary", "product_description", "problem_statement",
    "industry", "industry_mapped_id",
    "customer_segment", "customer_segment_other",
    "founder_reality_signals", "business_reality_signals", "invisible_gaps",
    "current_challenges", "current_challenges_other",
    "goal_90_day", "vision_1_year", "linkedin_url",
)


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

        # LEFT JOIN LATERAL rather than a subquery per column: the table is
        # append-only, so a founder can have many rows and a plain join would
        # multiply them. The lateral takes exactly the newest, and LEFT keeps
        # founders who have never answered the banner in the list -- they are
        # precisely who an admin is looking for.
        cookie_join = """
            left join lateral (
                select banner_action, created_at
                  from cookie_preferences cp
                 where cp.founder_id = f.founder_id
                 order by cp.created_at desc
                 limit 1
            ) ck on true"""
        rows = self.db.execute(text(f"""
            select {self._select_list()}, ck.banner_action as cookie_action
              from founders f{cookie_join}
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
                                     agree_diagnosis, age_confirmed, ip_address,
                                     consented_at
                                from founder_consents where founder_id = :fid
                               order by consented_at desc limit 1""", [])
        # Cookie choice is a SEPARATE consent under a separate legal basis, and
        # until now the panel could not show it at all: a founder who rejected
        # analytics looked identical to one who had never seen the banner.
        # Newest row wins -- the table is append-only, every change of mind is
        # its own row, and the current choice is the latest one.
        cookies = section("""select banner_action, necessary, analytics, marketing,
                                    functional, ip_address, created_at
                               from cookie_preferences where founder_id = :fid
                              order by created_at desc limit 1""", [])
        chat_rows = section("select count(*) as n from conversations where founder_id = :fid", [])

        return UserDetail(
            founder_id=founder_id,
            profile={k: f.get(k) for k in (
                "founder_id", "full_name", "email", "phone", "status", "plan_type",
                "created_at", "last_active_at", "admin_notes", "preferred_language",
                "profile_completed")},
            business={k: f.get(k) for k in (
                "business_name", "industry", "business_model", "team_size",
                "current_revenue", "website", "linkedin_url", "customer_segment",
                "problem_statement", "goal_90_day", "vision_1_year")},
            subscription=subs[0] if subs else None,
            credits={"balance": f.get("credits_balance", 0), "recent_transactions": txs},
            consent=consents[0] if consents else None,
            # None means the banner has never been answered by this founder --
            # distinct from an answer of "rejected everything", which is a row.
            cookie_consent=cookies[0] if cookies else None,
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
        """Erase the diagnosis so the founder can genuinely run another one.

        THIS USED TO CLEAR TWO COLUMNS AND NOTHING ELSE -- `diagnosis_used` and
        `diagnosis_locked_at` on `founders` -- which did not do what the button
        promised. The lifetime cap is not read from either of them: it counts
        COMPLETED ROWS in `sessions` (see count_completed_sessions in
        api/v1/diagnosis/repository.py, and the limit check in that package's
        service). So an admin pressed "Reset diagnosis", the panel reported
        rows affected, and the founder was still refused with
        DiagnosisAlreadyCompletedError the moment they tried again. The two
        columns drive the "diagnosis completed" display in the user list and
        nothing else.

        It now deletes the diagnosis itself, then clears those two columns so
        the display agrees with reality.

        One transaction, so a failure part-way through cannot leave a founder
        with half a diagnosis -- unlike the privacy deletion sweep, which
        deliberately takes a savepoint per table because it must continue past
        a failure to honour an erasure request. Here, stopping cleanly and
        changing nothing is the better outcome: the admin can look at the
        error and try again.
        """
        affected = 0
        try:
            for table in _DIAGNOSIS_TABLES:
                r = self.db.execute(
                    text(f"delete from {table} where founder_id = :fid"),  # noqa: S608
                    {"fid": founder_id})
                affected += r.rowcount or 0
            r = self.db.execute(
                text("""update founders
                           set diagnosis_used = 0, diagnosis_locked_at = null
                         where founder_id = :fid"""), {"fid": founder_id})
            affected += r.rowcount or 0
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return affected

    def reset_onboarding(self, founder_id: int) -> int:
        """Clear the founder's onboarding answers and send them back through it.

        `profile_completed` has to be written here explicitly. Everywhere else
        it is recomputed by FounderRepository.update() on the way past, but
        this repository writes SQL directly and never goes through it -- and
        leaving the flag true is not a cosmetic miss: GuidedLayout and the
        login redirect both read it, so the founder would be bounced straight
        to /app and would never see the questions whose answers we just
        deleted.

        The diagnosis is deliberately untouched. It is a separate action with
        its own button, and a founder correcting a wrong stage answer should
        not silently lose a report they spent an hour on.
        """
        assignments = ", ".join(f"{column} = null" for column in _ONBOARDING_COLUMNS)
        try:
            r = self.db.execute(
                text(f"""update founders
                            set {assignments},
                                profile_completed = false,
                                updated_at = now()
                          where founder_id = :fid"""),  # noqa: S608
                {"fid": founder_id})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
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


def _cookie_status(action: str | None) -> CookieStatus:
    try:
        return CookieStatus(action) if action else CookieStatus.NEVER_ANSWERED
    except ValueError:
        return CookieStatus.NEVER_ANSWERED


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
        # An unrecognised banner_action falls to NEVER_ANSWERED rather than
        # raising: an admin list must not 500 because one row holds a value the
        # CHECK constraint has since stopped allowing.
        cookie_status=_cookie_status(r.get("cookie_action")),
        created_at=r["created_at"],
        last_active_at=r.get("last_active_at"),
    )
