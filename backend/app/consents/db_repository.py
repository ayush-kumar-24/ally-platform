"""DB-backed consent store. Mirrors the app's other SQLAlchemy repositories
(commit + return the domain model). Untested in the hermetic suite (no live DB).

Only INSERT and SELECT appear here -- the ledger is append-only.
"""

from __future__ import annotations

from app.consents.db_models import ConsentRow
from app.consents.models import ConsentRecord
from app.consents.repository import ConsentRepository


class SqlAlchemyConsentRepository(ConsentRepository):
    def __init__(self, db):
        self.db = db

    def add(self, record: ConsentRecord) -> ConsentRecord:
        row = ConsentRow(
            consent_id=record.consent_id,
            founder_id=record.founder_id,
            terms_version=record.terms_version,
            privacy_version=record.privacy_version,
            agree_terms=record.agree_terms,
            agree_diagnosis=record.agree_diagnosis,
            consented_at=record.consented_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_domain(row)

    def latest(self, founder_id: int) -> ConsentRecord | None:
        row = (
            self.db.query(ConsentRow)
            .filter(ConsentRow.founder_id == founder_id)
            .order_by(ConsentRow.consented_at.desc(), ConsentRow.consent_id.desc())
            .first()
        )
        return _to_domain(row) if row is not None else None

    def list_for_founder(self, founder_id: int) -> list[ConsentRecord]:
        rows = (
            self.db.query(ConsentRow)
            .filter(ConsentRow.founder_id == founder_id)
            .order_by(ConsentRow.consented_at.desc(), ConsentRow.consent_id.desc())
            .all()
        )
        return [_to_domain(r) for r in rows]


def _to_domain(row: ConsentRow) -> ConsentRecord:
    return ConsentRecord(
        consent_id=row.consent_id,
        founder_id=row.founder_id,
        terms_version=row.terms_version,
        privacy_version=row.privacy_version,
        agree_terms=row.agree_terms,
        agree_diagnosis=row.agree_diagnosis,
        consented_at=row.consented_at,
    )
