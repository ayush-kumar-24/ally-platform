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

# Sections included in a self-service export, as (label, SQL). Each is scoped to the
# founder by :fid. Kept as an explicit list rather than "every table with a
# founder_id" so that adding a table is a deliberate disclosure decision.
#
# Originally 7 sections (founder_profile through tasks) -- the rest were added
# after a live audit found the export claimed "founder profile, sessions, and
# diagnosis history" while never actually including diagnosis sessions,
# Founder DNA, Current Problem, chat history, discovery calls, notifications,
# reports or feedback. `messages` has no founder_id of its own -- it joins
# through conversations, unlike every other section here.
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
    ("diagnosis_answers", "select * from answers where founder_id = :fid"),
    ("diagnosis_detected_root_causes",
     "select * from detected_root_causes where founder_id = :fid"),
    ("diagnosis_reports", "select * from founder_reports where founder_id = :fid"),
    ("stage_assessments",
     "select sa.* from stage_assessments sa "
     "join sessions s on s.session_id = sa.session_id where s.founder_id = :fid"),
    # --- founder dna / current problem -------------------------------------
    ("founder_dna_answers", "select * from founder_dna_answers where founder_id = :fid"),
    ("current_problem_answers",
     "select * from current_problem_answers where founder_id = :fid"),
    ("founder_context", "select * from founder_context where founder_id = :fid"),
    # --- chat history -------------------------------------------------------
    ("conversations", "select * from conversations where founder_id = :fid"),
    ("messages",
     "select m.* from messages m "
     "join conversations c on c.conversation_id = m.conversation_id "
     "where c.founder_id = :fid"),
    # --- everything else Ally holds under this founder_id -------------------
    ("discovery_calls", "select * from discovery_calls where founder_id = :fid"),
    ("notifications", "select * from notifications where founder_id = :fid"),
    ("founder_feedback", "select * from founder_feedback where founder_id = :fid"),
    ("token_usage", "select * from user_token_usage where founder_id = :fid"),
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
