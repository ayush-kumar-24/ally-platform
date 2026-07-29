"""Privacy requests repository.

Provides create + list_for_founder queries. Admin fulfilment
(update status, processing_notes, completed_at) is out of scope here —
that belongs in a future admin panel.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.schema import PrivacyRequests
from app.repositories.base import BaseRepository


class PrivacyRequestRepository(BaseRepository[PrivacyRequests]):
    def __init__(self) -> None:
        super().__init__(PrivacyRequests)

    def list_for_founder(
        self,
        db: Session,
        founder_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PrivacyRequests]:
        """Return a founder's privacy requests, newest first."""
        stmt = (
            select(PrivacyRequests)
            .where(PrivacyRequests.founder_id == founder_id)
            .order_by(PrivacyRequests.requested_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.execute(stmt).scalars().all())

    def count_for_founder(self, db: Session, founder_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(PrivacyRequests)
            .where(PrivacyRequests.founder_id == founder_id)
        )
        return db.execute(stmt).scalar_one()

    def submit(
        self,
        db: Session,
        founder_id: int,
        request_type: str,
        request_details: str | None = None,
    ) -> PrivacyRequests:
        """Create a new pending privacy request for this founder."""
        return self.create(
            db,
            {
                "founder_id": founder_id,
                "request_type": request_type,
                "request_details": request_details,
                "status": "pending",
            },
        )


privacy_request_repository = PrivacyRequestRepository()
