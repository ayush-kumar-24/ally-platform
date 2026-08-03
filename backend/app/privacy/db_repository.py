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

from app.privacy.errors import FounderNotFoundError
from app.privacy.models import ExportBundle, PrivacyAction, PrivacyState
from app.privacy.repository import PrivacyRepository

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
        row = self.db.execute(
            text("""select founder_id, processing_restricted_at,
                           deletion_requested_at, deletion_scheduled_at
                    from founders where founder_id = :fid"""),
            {"fid": founder_id},
        ).mappings().first()
        if row is None:
            raise FounderNotFoundError(founder_id)
        return PrivacyState(
            founder_id=row["founder_id"],
            processing_restricted=row["processing_restricted_at"] is not None,
            processing_restricted_at=row["processing_restricted_at"],
            deletion_requested_at=row["deletion_requested_at"],
            deletion_scheduled_at=row["deletion_scheduled_at"],
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


def _to_action(row) -> PrivacyAction:
    return PrivacyAction(
        request_id=row["request_id"], founder_id=row["founder_id"],
        request_type=row["request_type"], status=row["status"],
        requested_at=row["requested_at"], due_by=row["due_by"],
    )
