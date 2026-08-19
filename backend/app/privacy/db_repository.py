"""DB-backed privacy store.

Restriction/deletion state lives on the `founders` row (alongside the existing
`deletion_requested_at` / `deletion_scheduled_at` columns) and the audit trail uses
the existing `privacy_requests` table -- neither is duplicated here.

Untested in the hermetic suite (no live DB); the service is covered via the
in-memory repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.privacy.errors import (
    FounderNotFoundError,
    NoDeletionToCancelError,
    PrivacyRequestNotFoundError,
)
from app.privacy.models import ExportBundle, PrivacyAction, PrivacyState
from app.privacy.repository import PrivacyRepository

# The diagnosis half of this list was missing, and the omission was not small:
# the Privacy Center screen offers "a full export (JSON) of all data Ally holds
# about you -- founder profile, SESSIONS, and DIAGNOSIS HISTORY", while the
# export returned profile/consents/settings/planning only. Measured on one
# account: 5 records returned against 51 actually held. Under DPDP and GDPR
# right-of-access that gap is the defect, so the tables the sentence already
# promises are now included.
#
# Answers are joined to their question text on purpose. A portability export has
# to be intelligible to the person receiving it, and a bare `question_id` is not
# -- it is a foreign key into a catalogue they cannot see.
_EXPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("founder_profile", "select * from founders where founder_id = :fid"),
    ("consents", "select * from founder_consents where founder_id = :fid"),
    ("privacy_requests", "select * from privacy_requests where founder_id = :fid"),
    ("settings", "select * from founder_settings where founder_id = :fid"),
    ("plans", "select * from planning_plans where founder_id = :fid"),
    ("goals", "select * from planning_goals where founder_id = :fid"),
    ("tasks", "select * from planning_tasks where founder_id = :fid"),
    # --- diagnosis history ------------------------------------------------
    ("diagnosis_sessions", "select * from sessions where founder_id = :fid"),
    (
        "diagnosis_answers",
        "select a.*, q.question_text, q.category, q.question_code "
        "from answers a left join questions q on q.question_id = a.question_id "
        "where a.founder_id = :fid order by a.answered_at",
    ),
    (
        "founder_dna_answers",
        "select a.*, q.question_text, q.dimension_code "
        "from founder_dna_answers a "
        "left join founder_dna_questions q "
        "  on q.founder_dna_question_id = a.founder_dna_question_id "
        "where a.founder_id = :fid order by a.answered_at",
    ),
    (
        "current_problem_answers",
        "select a.*, q.question_text "
        "from current_problem_answers a "
        "left join current_problem_questions q "
        "  on q.current_problem_question_id = a.current_problem_question_id "
        "where a.founder_id = :fid order by a.answered_at",
    ),
    ("stage_assessments", "select * from stage_assessments where founder_id = :fid"),
    ("detected_root_causes", "select * from detected_root_causes where founder_id = :fid"),
    ("reports", "select * from founder_reports where founder_id = :fid"),
    ("feedback", "select * from founder_feedback where founder_id = :fid"),
    # --- what Ally remembers about them -----------------------------------
    ("founder_context", "select * from founder_context where founder_id = :fid"),
    ("founder_memory", "select * from founder_memory where founder_id = :fid"),
    ("founder_memory_events", "select * from founder_memory_events where founder_id = :fid"),
    # --- chat --------------------------------------------------------------
    ("conversations", "select * from conversations where founder_id = :fid"),
    (
        "messages",
        "select * from messages where founder_id = :fid order by created_at",
    ),
    # --- everything else Ally holds under this founder_id -------------------
    # (discovery_calls / notifications / token_usage: found missing in the same
    # audit that found the diagnosis history gap above.)
    ("discovery_calls", "select * from discovery_calls where founder_id = :fid"),
    ("notifications", "select * from notifications where founder_id = :fid"),
    ("token_usage", "select * from user_token_usage where founder_id = :fid"),
)

# Deliberately NOT exported: `internal_intelligence_reports`.
#
# It is derived from this founder's data and therefore arguably personal data
# under a right-of-access request, but it is also Ally's internal commercial
# assessment. Which way that resolves is a legal call, not an engineering one,
# so the status quo (excluded) is preserved rather than quietly changed here.
# If counsel says it must be disclosed, add it to the tuple above -- nothing
# else needs to change.


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
        self.db.commit()
        return self.get_state(founder_id)

    # --- audit trail ----------------------------------------------------

    def log_request(self, founder_id: int, *, request_type: str, details: str | None,
                    at: datetime, due_by: datetime | None) -> PrivacyAction:
        row = self.db.execute(
            text("""insert into privacy_requests
                        (founder_id, request_type, status, request_details, requested_at, due_by)
                    values (:fid, :rt, 'pending', :det, :at, :due)
                    returning request_id, founder_id, request_type, status, requested_at, due_by,
                              request_details, processed_by, processing_notes, rejection_reason,
                              completed_at"""),
            {"fid": founder_id, "rt": request_type, "det": details, "at": at, "due": due_by},
        ).mappings().first()
        self.db.commit()
        return _to_action(row)

    def list_requests(self, founder_id: int) -> list[PrivacyAction]:
        rows = self.db.execute(
            text("""select request_id, founder_id, request_type, status, requested_at, due_by,
                           request_details, processed_by, processing_notes, rejection_reason,
                           completed_at
                      from privacy_requests
                     where founder_id = :fid
                     order by requested_at desc, request_id desc"""),
            {"fid": founder_id},
        ).mappings().all()
        return [_to_action(r) for r in rows]

    # --- admin fulfilment -------------------------------------------------

    def list_all_requests(self, *, status: str | None = None,
                          limit: int = 50, offset: int = 0) -> list[PrivacyAction]:
        """Admin-wide view across every founder's requests -- backs the panel's
        review queue. Unlike list_requests, not scoped to one founder."""
        rows = self.db.execute(
            text("""select request_id, founder_id, request_type, status, requested_at, due_by,
                           request_details, processed_by, processing_notes, rejection_reason,
                           completed_at
                      from privacy_requests
                     where CAST(:status AS VARCHAR) is null or status = CAST(:status AS VARCHAR)
                     order by requested_at desc, request_id desc
                     limit :lim offset :off"""),
            {"status": status, "lim": limit, "off": offset},
        ).mappings().all()
        return [_to_action(r) for r in rows]

    def resolve_request(self, request_id: int, *, status: str, processed_by: str,
                        processing_notes: str | None, rejection_reason: str | None,
                        at: datetime) -> PrivacyAction:
        row = self.db.execute(
            text("""update privacy_requests
                       set status = :status,
                           processed_by = :by,
                           processing_notes = :notes,
                           rejection_reason = :reason,
                           completed_at = case when CAST(:status AS VARCHAR) in ('completed', 'rejected')
                                               then :at else completed_at end
                     where request_id = :rid
                    returning request_id, founder_id, request_type, status, requested_at, due_by,
                              request_details, processed_by, processing_notes, rejection_reason,
                              completed_at"""),
            {"status": status, "by": processed_by, "notes": processing_notes,
             "reason": rejection_reason, "at": at, "rid": request_id},
        ).mappings().first()
        if row is None:
            self.db.rollback()
            raise PrivacyRequestNotFoundError(request_id)
        self.db.commit()
        return _to_action(row)

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
    # .get() rather than [] -- defensive against a future call site that
    # selects a narrower column set, rather than a hard KeyError.
    return PrivacyAction(
        request_id=row["request_id"], founder_id=row["founder_id"],
        request_type=row["request_type"], status=row["status"],
        requested_at=row["requested_at"], due_by=row["due_by"],
        request_details=row.get("request_details"), processed_by=row.get("processed_by"),
        processing_notes=row.get("processing_notes"), rejection_reason=row.get("rejection_reason"),
        completed_at=row.get("completed_at"),
    )
