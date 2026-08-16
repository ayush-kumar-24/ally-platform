"""DB-backed privacy store.

Restriction/deletion state lives on the `founders` row (alongside the existing
`deletion_requested_at` / `deletion_scheduled_at` columns) and the audit trail uses
the existing `privacy_requests` table -- neither is duplicated here.

Untested in the hermetic suite (no live DB); the service is covered via the
in-memory repository.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text

from app.privacy.errors import FounderNotFoundError, NoDeletionToCancelError
from app.privacy.models import ExportBundle, PrivacyAction, PrivacyState
from app.privacy.repository import PrivacyRepository
# Restored during the origin/main merge: SqlAlchemyDeletionRepository below is
# local-only (upstream has no such class), so its base class import was dropped
# when this file's conflicting hunks resolved to the upstream side. See the
# NoDeletionPendingError note in errors.py -- the duplicate deletion pipelines
# still need reconciling; this only keeps the module importable meanwhile.
from app.privacy.deletion_repository import DeletionRepository

# Sections included in a self-service export, as (label, SQL). Each is scoped to the
# founder by :fid. Kept as an explicit list rather than "every table with a
# founder_id" so that adding a table is a deliberate disclosure decision.
_EXPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("founder_profile", "select * from founders where founder_id = :fid"),
    ("consents", "select * from founder_consents where founder_id = :fid"),
    ("privacy_requests", "select * from privacy_requests where founder_id = :fid"),
    ("settings", "select * from founder_settings where founder_id = :fid"),
    ("plans", "select * from planning_plans where founder_id = :fid"),
    ("goals", "select * from planning_goals where founder_id = :fid"),
    ("tasks", "select * from planning_tasks where founder_id = :fid"),
)


class SqlAlchemyPrivacyRepository(PrivacyRepository):
    def __init__(self, db):
        self.db = db

    # --- export ---------------------------------------------------------

    def gather_export(self, founder_id: int, generated_at: datetime) -> ExportBundle:
        sections: dict = {}
        for label, sql in _EXPORT_SECTIONS:
            try:
                rows = self.db.execute(text(sql), {"fid": founder_id}).mappings().all()
                sections[label] = [dict(r) for r in rows]
            except Exception:
                # A table that does not exist in this environment must not abort the
                # whole export -- the founder still has a right to the rest. The
                # section is marked so the gap is visible rather than silent.
                self.db.rollback()
                sections[label] = {"unavailable": True}
        return ExportBundle(founder_id=founder_id, generated_at=generated_at, sections=sections)

    # --- state ----------------------------------------------------------

    def get_state(self, founder_id: int) -> PrivacyState:
        # `processing_restricted_at` / `deletion_executed_at` each arrived with
        # their own migration that may not have run yet in every environment.
        # Falling back keeps the Privacy Center usable instead of 500-ing the
        # whole page over one absent column.
        try:
            row = self.db.execute(
                text("""select founder_id, processing_restricted_at,
                               deletion_requested_at, deletion_scheduled_at,
                               deletion_executed_at
                        from founders where founder_id = :fid"""),
                {"fid": founder_id},
            ).mappings().first()
        except Exception:
            self.db.rollback()
            legacy = self.db.execute(
                text("""select founder_id, deletion_requested_at, deletion_scheduled_at
                        from founders where founder_id = :fid"""),
                {"fid": founder_id},
            ).mappings().first()
            row = (dict(legacy) | {"processing_restricted_at": None, "deletion_executed_at": None}
                   if legacy else None)
        if row is None:
            raise FounderNotFoundError(founder_id)
        return PrivacyState(
            founder_id=row["founder_id"],
            processing_restricted=row["processing_restricted_at"] is not None,
            processing_restricted_at=row["processing_restricted_at"],
            deletion_requested_at=row["deletion_requested_at"],
            deletion_scheduled_at=row["deletion_scheduled_at"],
            deletion_executed_at=row.get("deletion_executed_at"),
        )

    def set_restriction(self, founder_id: int, *, restricted: bool, at: datetime) -> PrivacyState:
        self.db.execute(
            text("update founders set processing_restricted_at = :at where founder_id = :fid"),
            {"at": at if restricted else None, "fid": founder_id},
        )
        self.db.commit()
        return self.get_state(founder_id)

    def schedule_deletion(self, founder_id: int, *, requested_at: datetime,
                          scheduled_at: datetime) -> PrivacyState:
        self.db.execute(
            text("""update founders
                       set deletion_requested_at = :req, deletion_scheduled_at = :sch
                     where founder_id = :fid"""),
            {"req": requested_at, "sch": scheduled_at, "fid": founder_id},
        )
        # Committed before the (best-effort) tracking-row upsert below, so a schema
        # mismatch on that table can never roll back the founders write that actually
        # implements the right being exercised.
        self.db.commit()
        self._upsert_deletion_request(founder_id, requested_at=requested_at,
                                       grace_period_ends_at=scheduled_at, status="grace_period")
        return self.get_state(founder_id)

    def cancel_deletion(self, founder_id: int, *, at: datetime) -> PrivacyState:
        self.db.execute(
            text("""update founders
                       set deletion_requested_at = null, deletion_scheduled_at = null
                     where founder_id = :fid"""),
            {"fid": founder_id},
        )
        self.db.commit()
        try:
            self.db.execute(
                text("""update data_deletion_requests
                           set status = 'cancelled', cancellation_requested_at = :at
                         where founder_id = :fid and status in ('pending_otp', 'grace_period')"""),
                {"at": at, "fid": founder_id},
            )
            self.db.commit()
        except Exception:
            # The tracking table is a nice-to-have for the executor/admin view; the
            # authoritative state is the founders columns cleared above, so a schema
            # mismatch here must not resurface as a failed cancellation.
            self.db.rollback()
        return self.get_state(founder_id)

    def _upsert_deletion_request(self, founder_id: int, *, requested_at: datetime,
                                  grace_period_ends_at: datetime, status: str) -> None:
        try:
            existing = self.db.execute(
                text("select deletion_id from data_deletion_requests where founder_id = :fid"),
                {"fid": founder_id},
            ).scalar()
            if existing is None:
                self.db.execute(
                    text("""insert into data_deletion_requests
                                (founder_id, requested_at, status, grace_period_ends_at,
                                 otp_verified, confirmation_email_sent)
                            values (:fid, :req, :status, :grace, true, false)"""),
                    {"fid": founder_id, "req": requested_at, "status": status,
                     "grace": grace_period_ends_at},
                )
            else:
                self.db.execute(
                    text("""update data_deletion_requests
                               set requested_at = :req, status = :status,
                                   grace_period_ends_at = :grace,
                                   cancellation_requested_at = null,
                                   deletion_completed_at = null
                             where founder_id = :fid"""),
                    {"fid": founder_id, "req": requested_at, "status": status,
                     "grace": grace_period_ends_at},
                )
            self.db.commit()
        except Exception:
            self.db.rollback()

    # --- audit trail ----------------------------------------------------

    def log_request(self, founder_id: int, *, request_type: str, details: str | None,
                    at: datetime, due_by: datetime | None) -> PrivacyAction:
        row = self.db.execute(
            text("""insert into privacy_requests
                        (founder_id, request_type, status, request_details, requested_at, due_by)
                    values (:fid, :rt, 'pending', :det, :at, :due)
                    returning request_id, founder_id, request_type, status, requested_at, due_by"""),
            {"fid": founder_id, "rt": request_type, "det": details, "at": at, "due": due_by},
        ).mappings().first()
        self.db.commit()
        return _to_action(row)

    def list_requests(self, founder_id: int) -> list[PrivacyAction]:
        rows = self.db.execute(
            text("""select request_id, founder_id, request_type, status, requested_at, due_by
                      from privacy_requests
                     where founder_id = :fid
                     order by requested_at desc, request_id desc"""),
            {"fid": founder_id},
        ).mappings().all()
        return [_to_action(r) for r in rows]

    # --- execution ---------------------------------------------------------

    def find_due_for_deletion(self, now: datetime) -> list[int]:
        rows = self.db.execute(
            text("""select founder_id from founders
                     where deletion_scheduled_at is not null
                       and deletion_scheduled_at <= :now
                       and deletion_executed_at is null
                     order by deletion_scheduled_at asc"""),
            {"now": now},
        ).all()
        return [r[0] for r in rows]

    def cancel_deletion(self, founder_id: int) -> PrivacyState:
        state = self.get_state(founder_id)
        if not state.deletion_pending:
            raise NoDeletionToCancelError(founder_id)
        self.db.execute(
            text("""update founders
                       set deletion_requested_at = null, deletion_scheduled_at = null
                     where founder_id = :fid"""),
            {"fid": founder_id},
        )
        self.db.commit()
        return self.get_state(founder_id)


def _to_action(row) -> PrivacyAction:
    return PrivacyAction(
        request_id=row["request_id"], founder_id=row["founder_id"],
        request_type=row["request_type"], status=row["status"],
        requested_at=row["requested_at"], due_by=row["due_by"],
    )


# --- deletion executor's production store -----------------------------------

# Tables purged outright: the founder's activity/content data, deleted rather than
# anonymised because there is no legitimate reason to keep a trace of it once the
# grace period has passed. Each entry is (label, DELETE sql) -- same explicit-list
# discipline as `_EXPORT_SECTIONS` above, so adding a table here is a deliberate
# decision, not something a future migration does by accident.
_PURGE_TABLES: tuple[tuple[str, str], ...] = (
    ("conversations", "delete from conversations where founder_id = :fid"),
    ("sessions", "delete from sessions where founder_id = :fid"),
    ("answers", "delete from answers where founder_id = :fid"),
    ("detected_root_causes", "delete from detected_root_causes where founder_id = :fid"),
    ("founder_reports", "delete from founder_reports where founder_id = :fid"),
    ("internal_intelligence_reports",
     "delete from internal_intelligence_reports where founder_id = :fid"),
    ("stage_assessments", "delete from stage_assessments where founder_id = :fid"),
    ("rag_retrieval_log", "delete from rag_retrieval_log where founder_id = :fid"),
    ("founder_feedback", "delete from founder_feedback where founder_id = :fid"),
    ("discovery_calls", "delete from discovery_calls where founder_id = :fid"),
    ("daily_actions", "delete from daily_actions where founder_id = :fid"),
    ("planning_tasks", """delete from planning_tasks where plan_id in
                            (select plan_id from planning_plans where founder_id = :fid)"""),
    ("planning_goals", """delete from planning_goals where plan_id in
                            (select plan_id from planning_plans where founder_id = :fid)"""),
    ("planning_plans", "delete from planning_plans where founder_id = :fid"),
    ("notifications", "delete from notifications where founder_id = :fid"),
    ("cookie_preferences", "delete from cookie_preferences where founder_id = :fid"),
    ("founder_context", "delete from founder_context where founder_id = :fid"),
    ("founder_visual_choices", "delete from founder_visual_choices where founder_id = :fid"),
    ("user_token_usage", "delete from user_token_usage where founder_id = :fid"),
    ("file_uploads", "delete from file_uploads where founder_id = :fid"),
    ("report_shares", "delete from report_shares where founder_id = :fid"),
)

# Tables deliberately RETAINED rather than purged, and why -- not silently skipped,
# so a reviewer can see this was a decision:
#   payments, subscriptions      billing/tax records; Art 17(3)(b) legal obligation
#   privacy_requests             the DSAR audit trail itself (Art 5(2) accountability)
#   data_deletion_requests       this erasure's own record -- see the module docstring
#   consents, consent_history    evidence of what was agreed and when, for defending
#                                 against a future claim that consent was never given
#   admin_notes                  admin-authored, not founder-authored content
#   webhook_logs                 founder_id is ON DELETE SET NULL; decouples on its own


class SqlAlchemyDeletionRepository(DeletionRepository):
    """Production store for the deletion executor. See `app/privacy/executor.py`
    for why this anonymises the founders row rather than deleting it."""

    def __init__(self, db):
        self.db = db

    def list_due(self, *, now: datetime, limit: int) -> list[DueDeletion]:
        rows = self.db.execute(
            text("""select deletion_id, founder_id, requested_at, grace_period_ends_at
                      from data_deletion_requests
                     where status = 'grace_period' and grace_period_ends_at <= :now
                     order by grace_period_ends_at asc
                     limit :lim"""),
            {"now": now, "lim": limit},
        ).mappings().all()
        return [DueDeletion(deletion_id=r["deletion_id"], founder_id=r["founder_id"],
                            requested_at=r["requested_at"],
                            grace_period_ends_at=r["grace_period_ends_at"]) for r in rows]

    def ensure_immediate(self, founder_id: int, *, at: datetime) -> int:
        existing = self.db.execute(
            text("""select deletion_id from data_deletion_requests
                     where founder_id = :fid and status in ('pending_otp', 'grace_period')"""),
            {"fid": founder_id},
        ).scalar()
        if existing is not None:
            self.db.execute(
                text("""update data_deletion_requests
                           set grace_period_ends_at = :at where deletion_id = :id"""),
                {"id": existing, "at": at},
            )
            self.db.commit()
            return int(existing)

        row = self.db.execute(
            text("""insert into data_deletion_requests
                        (founder_id, requested_at, status, grace_period_ends_at,
                         otp_verified, confirmation_email_sent)
                    values (:fid, :at, 'grace_period', :at, true, false)
                    returning deletion_id"""),
            {"fid": founder_id, "at": at},
        ).scalar()
        # Also stamp the founders columns so PrivacyService.get_state reflects the
        # same standing an executed-later request would have shown along the way.
        self.db.execute(
            text("""update founders set deletion_requested_at = :at, deletion_scheduled_at = :at
                     where founder_id = :fid"""),
            {"fid": founder_id, "at": at},
        )
        self.db.commit()
        return int(row)

    def mark_processing(self, deletion_id: int) -> None:
        self.db.execute(
            text("update data_deletion_requests set status = 'processing' where deletion_id = :id"),
            {"id": deletion_id},
        )
        self.db.commit()

    def purge_founder(self, founder_id: int, *, at: datetime) -> dict:
        summary: dict[str, object] = {}
        for label, sql in _PURGE_TABLES:
            try:
                result = self.db.execute(text(sql), {"fid": founder_id})
                summary[label] = result.rowcount or 0
                self.db.commit()
            except Exception as exc:                                # noqa: BLE001 - recorded, not hidden
                # One absent/renamed table must not abort the whole erasure -- the
                # gap is recorded in the summary (and therefore in
                # data_types_deleted) instead of silently skipped.
                self.db.rollback()
                summary[label] = f"error: {exc.__class__.__name__}"

        summary["founder_profile"] = self._anonymise_founder(founder_id, at=at)
        return summary

    def _anonymise_founder(self, founder_id: int, *, at: datetime) -> str:
        try:
            self.db.execute(
                text("""update founders set
                            full_name = 'Deleted Founder',
                            email = :anon_email,
                            website = null, linkedin_url = null,
                            social_profiles = '{}'::jsonb,
                            problem_statement = null, goal_90_day = null, vision_1_year = null,
                            founder_motivation = null, building_summary = null,
                            adaptive_reflection = null,
                            customer_segment = '[]'::jsonb, customer_segment_other = null,
                            current_challenges = '[]'::jsonb, emotional_state = '[]'::jsonb,
                            support_preferences = '[]'::jsonb,
                            updated_at = :at
                        where founder_id = :fid"""),
                {"fid": founder_id, "anon_email": f"deleted-{founder_id}@erased.goxl.in", "at": at},
            )
            self.db.commit()
            return "anonymised"
        except Exception as exc:                                    # noqa: BLE001
            self.db.rollback()
            return f"error: {exc.__class__.__name__}"

    def mark_completed(self, deletion_id: int, *, at: datetime, data_types_deleted: dict) -> None:
        self.db.execute(
            text("""update data_deletion_requests
                       set status = 'completed', deletion_completed_at = :at,
                           data_types_deleted = cast(:types as jsonb)
                     where deletion_id = :id"""),
            {"id": deletion_id, "at": at, "types": json.dumps(data_types_deleted, default=str)},
        )
        self.db.commit()

    def mark_failed(self, deletion_id: int, *, reason: str) -> None:
        self.db.execute(
            text("update data_deletion_requests set status = 'grace_period' where deletion_id = :id"),
            {"id": deletion_id},
        )
        self.db.commit()
