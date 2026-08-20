"""SQLAlchemy-backed FrameworkUsageRepository (production).

Maps ORM rows <-> frozen domain models. Untested in the hermetic suite (no
live DB); mirrors app/vision/db_repository.py's get-then-add-or-update
upsert shape.
"""

from __future__ import annotations

from app.framework_usage.db_models import FrameworkUsageRow
from app.framework_usage.models import FrameworkUsage
from app.framework_usage.repository import FrameworkUsageRepository


def _to_domain(row: FrameworkUsageRow) -> FrameworkUsage:
    return FrameworkUsage(
        founder_id=row.founder_id, framework_id=row.framework_id,
        last_used_at=row.last_used_at, note=row.note,
    )


class SqlAlchemyFrameworkUsageRepository(FrameworkUsageRepository):
    def __init__(self, db):
        self.db = db

    def get(self, founder_id: int, framework_id: str) -> FrameworkUsage | None:
        row = self.db.get(FrameworkUsageRow, {"founder_id": founder_id, "framework_id": framework_id})
        return _to_domain(row) if row is not None else None

    def list_for_founder(self, founder_id: int) -> tuple[FrameworkUsage, ...]:
        rows = (
            self.db.query(FrameworkUsageRow)
            .filter(FrameworkUsageRow.founder_id == founder_id)
            .order_by(FrameworkUsageRow.last_used_at.desc())
            .all()
        )
        return tuple(_to_domain(r) for r in rows)

    def upsert(self, usage: FrameworkUsage) -> FrameworkUsage:
        row = self.db.get(FrameworkUsageRow, {"founder_id": usage.founder_id, "framework_id": usage.framework_id})
        if row is None:
            row = FrameworkUsageRow(founder_id=usage.founder_id, framework_id=usage.framework_id)
            self.db.add(row)
        row.last_used_at, row.note = usage.last_used_at, usage.note
        self.db.commit()
        return usage
