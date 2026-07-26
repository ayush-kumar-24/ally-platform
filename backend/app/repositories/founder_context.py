from sqlalchemy.orm import Session

from app.models.schema import FounderContext
from app.repositories.base import BaseRepository


class FounderContextRepository(BaseRepository[FounderContext]):
    def __init__(self) -> None:
        super().__init__(FounderContext)

    def get_by_founder(self, db: Session, founder_id: int) -> FounderContext | None:
        return self.get_by(db, founder_id=founder_id)

    def upsert(self, db: Session, founder_id: int, data: dict) -> FounderContext:
        """One row per founder (founder_id is unique): update it, or create it."""
        existing = self.get_by_founder(db, founder_id)
        if existing is not None:
            return self.update(db, existing, data)
        return self.create(db, {"founder_id": founder_id, **data})


founder_context_repository = FounderContextRepository()
