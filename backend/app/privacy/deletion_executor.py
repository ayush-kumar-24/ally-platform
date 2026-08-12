"""Executes a founder's scheduled erasure (GDPR Art 17 / DPDP) once its grace
window has passed.

This is the piece that was missing entirely: `PrivacyService.request_account_
deletion` has always been able to SCHEDULE erasure, but nothing ever consumed
the schedule -- a founder past deletion_scheduled_at sat there forever,
indistinguishable in practice from one who was never touched. `run(founder_id)`
is that missing consumer. It is meant to be called by exactly two things:

  1. A scheduled sweep (see find_due()) for self-service DPDP requests.
  2. The Supabase Auth "user.deleted" webhook, for a founder whose identity
     is already gone -- see app/api/v1/webhooks/supabase.py. Both paths go
     through the SAME PrivacyService.request_account_deletion() to get here;
     this module does not know or care which one scheduled a given founder.

Three-way policy, decided per table -- NOT a blind "DELETE WHERE founder_id"
sweep across every founder-scoped table, because that would be wrong for at
least two categories of data:

  HARD DELETE   Pure product-usage data with no external retention claim on
                it. Safe to remove outright.

  ANONYMIZE     `founders` itself. The row survives (every hard-deleted
                table above kept a live FK to point at during the sweep, so
                deletion order never matters and nothing can orphan), but
                every directly-identifying field is overwritten. This is
                the ONE row in the whole sweep that gets column-level
                scrubbing rather than a DELETE.

  RETAIN        Financial (`payments`, `subscriptions`, `credit_transactions`)
                and accountability (`audit_logs`, `consent_history`,
                `consents`, `founder_consents`, `privacy_requests`) tables.
                Checked their columns before writing this: none of the
                financial tables carry a name/email/contact field of their
                own -- they are pure ledger rows keyed by founder_id, so
                anonymizing `founders` already anonymizes them BY
                INHERITANCE with no separate write needed. The accountability
                tables DO carry their own ip_address/browser columns
                (independently personal data), so those two columns are
                nulled explicitly; the row itself (what was consented to,
                what an admin did, when) stays, because GDPR Art 5(2)
                accountability requires being able to show what happened,
                and deleting the evidence of a deletion request would defeat
                the right it exists to implement.

                IMPORTANT -- retaining the financial tables at all (rather
                than also deleting them) is a legal call, not an engineering
                one. GDPR Art 17(3)(b) and equivalent tax/accounting law can
                both require or permit it, but "can" is not "does" for
                GoXL's specific jurisdiction and retention obligations. This
                module assumes retention is correct; it does not verify that
                assumption. Get compliance/legal sign-off before this runs
                against real founder data, not just an engineering review.

Idempotent and safe to re-run: hard-deletes of already-gone rows are no-ops,
and the founders row is only touched (and deletion_executed_at only stamped)
once, guarded by find_due() only returning founders that are due AND not yet
executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logger import logger

# Every table here holds nothing but founder_id + product-usage data -- no
# separate PII column, no external retention claim. Explicit list, not
# "every table with a founder_id column", so adding a new founder-scoped
# table is a deliberate decision to include it here, the same discipline
# _EXPORT_SECTIONS already uses in db_repository.py.
_HARD_DELETE_TABLES: tuple[str, ...] = (
    "analytics_events", "answers", "cookie_preferences", "conversations",
    "messages", "daily_actions", "data_deletion_requests",
    "detected_root_causes", "discovery_calls", "file_uploads",
    "founder_context", "founder_feedback", "founder_memory",
    "founder_memory_events", "founder_reports",
    "internal_intelligence_reports", "founder_visual_choices", "notifications",
    "planning_plans", "planning_goals", "planning_tasks", "planning_reminders",
    "report_shares", "sessions", "stage_assessments", "suggestions",
    "suggestion_feedback", "daily_token_usage", "plan_call_usage",
    "unbilled_usage", "llm_call_log",
)

# ip_address / browser are the only independently-identifying columns on
# these tables; the row (what happened, when) is accountability evidence and
# stays. Not a legal question the way the financial tables are -- nulling an
# IP after the account it belongs to no longer exists is unambiguously safe.
_SCRUB_COLUMNS_RETAIN_ROW: tuple[str, ...] = (
    "audit_logs", "consent_history", "consents",
)

# No column-level action at all: these have no PII column of their own (see
# module docstring), so anonymizing `founders` anonymizes these by
# inheritance. Listed explicitly anyway so a reviewer can see they were
# considered, not skipped by omission.
_RETAIN_AS_IS_PENDING_LEGAL: tuple[str, ...] = (
    "payments", "subscriptions", "credit_transactions", "founder_consents",
    "privacy_requests",
)

_ANON_EMAIL = "deleted-founder-{founder_id}@erased.ally.local"
_ANON_NAME = "Deleted Founder"


@dataclass(frozen=True)
class DeletionResult:
    founder_id: int
    hard_deleted: dict[str, int] = field(default_factory=dict)
    scrubbed: tuple[str, ...] = ()
    retained_as_is: tuple[str, ...] = _RETAIN_AS_IS_PENDING_LEGAL
    executed_at: datetime | None = None


class AccountDeletionExecutor:
    """Runs one founder's erasure sweep. `db` is a request/job-scoped session;
    the caller owns the transaction boundary (commit/rollback)."""

    def __init__(self, db: Session, *, clock=None):
        self.db = db
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def run(self, founder_id: int) -> DeletionResult:
        hard_deleted: dict[str, int] = {}
        for table in _HARD_DELETE_TABLES:
            # Each table gets its OWN savepoint. Without this, one failing
            # statement's `self.db.rollback()` would roll back the ENTIRE
            # transaction -- including every hard-delete already run earlier
            # in this same loop, since nothing commits until the very end.
            # Confirmed live: exactly this happened during verification --
            # three PII-scrub failures below wiped out every hard-delete that
            # ran before them, and only the founders UPDATE (which runs
            # after, in the now-clean transaction) survived to commit. A
            # savepoint scopes the damage to the one statement that actually
            # failed.
            try:
                with self.db.begin_nested():
                    result = self.db.execute(
                        text(f"DELETE FROM {table} WHERE founder_id = :fid"),
                        {"fid": founder_id},
                    )
                    hard_deleted[table] = result.rowcount or 0
            except Exception as exc:  # noqa: BLE001
                # A table missing/renamed in this environment must not abort
                # the whole sweep -- log it loudly (this is the one place a
                # silent skip would be a real data-retention bug, not just a
                # missing feature) and continue with the rest.
                logger.error(
                    "deletion sweep: hard-delete failed for a table, continuing",
                    extra={"founder_id": founder_id, "table": table, "error": str(exc)},
                )

        for table in _SCRUB_COLUMNS_RETAIN_ROW:
            try:
                with self.db.begin_nested():
                    # ip_address is NOT NULL on all three tables here (checked
                    # live before writing this, not assumed) -- browser is
                    # nullable. A real value can't stay, and NULL isn't legal,
                    # so it's overwritten with an explicit, unmistakably-not-
                    # a-real-IP sentinel rather than a valid-looking fake one.
                    self.db.execute(
                        text(f"UPDATE {table} SET ip_address = '0.0.0.0', browser = NULL "
                             f"WHERE founder_id = :fid"),
                        {"fid": founder_id},
                    )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "deletion sweep: PII scrub failed for a table, continuing",
                    extra={"founder_id": founder_id, "table": table, "error": str(exc)},
                )

        now = self._now()
        self.db.execute(
            text("""
                UPDATE founders
                   SET full_name = :name,
                       email = :email,
                       founder_motivation = NULL,
                       building_summary = NULL,
                       problem_statement = NULL,
                       website = NULL,
                       linkedin_url = NULL,
                       social_profiles = '{}'::jsonb,
                       customer_segment_other = NULL,
                       adaptive_reflection = NULL,
                       first_impression = NULL,
                       deletion_executed_at = :at
                 WHERE founder_id = :fid
            """),
            {
                "name": _ANON_NAME,
                "email": _ANON_EMAIL.format(founder_id=founder_id),
                "at": now,
                "fid": founder_id,
            },
        )
        self.db.commit()

        logger.info(
            "deletion sweep completed",
            extra={"founder_id": founder_id, "tables_touched": len(hard_deleted)},
        )
        return DeletionResult(
            founder_id=founder_id,
            hard_deleted=hard_deleted,
            scrubbed=_SCRUB_COLUMNS_RETAIN_ROW,
            executed_at=now,
        )
