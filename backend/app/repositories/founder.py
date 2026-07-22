"""Founder repository -- the one concrete example wired into a live route.

Shows the pattern: subclass BaseRepository, add only the model-specific lookups.
Other models get their own repository the same way as features need them.
"""

from sqlalchemy.orm import Session

from app.models import Founder
from app.repositories.base import BaseRepository


class FounderRepository(BaseRepository[Founder]):
    def __init__(self) -> None:
        super().__init__(Founder)

    def get_by_user_id(self, db: Session, user_id) -> Founder | None:
        """Look up a founder by the Supabase auth uid carried in the token."""
        return self.get_by(db, user_id=user_id)


# Repositories are stateless -- one shared instance is fine.
founder_repository = FounderRepository()
