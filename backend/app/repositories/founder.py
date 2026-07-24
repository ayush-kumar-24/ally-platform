"""Founder repository -- the one concrete example wired into a live route.

Shows the pattern: subclass BaseRepository, add only the model-specific lookups.
Other models get their own repository the same way as features need them.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Founder
from app.repositories.base import BaseRepository


class FounderRepository(BaseRepository[Founder]):
    def __init__(self) -> None:
        super().__init__(Founder)

    def get_by_user_id(self, db: Session, user_id) -> Founder | None:
        """Look up a founder by the Supabase auth uid carried in the token."""
        return self.get_by(db, user_id=user_id)

    def resolve_stage_id(self, db: Session, stage: str) -> int | None:
        """Turn a stage name/label ('Validation', 'Stage 0->1', or '2') into a
        founder_stages.stage_id -- the same resolution the onboarding function
        uses, so the API and the DB agree. Returns None if it can't be matched.
        """
        row = db.execute(
            text(
                "SELECT stage_id FROM founder_stages "
                "WHERE lower(stage_name) = lower(btrim(:s)) "
                "   OR lower(onboarding_label) = lower(btrim(:s)) "
                "ORDER BY stage_order LIMIT 1"
            ),
            {"s": stage},
        ).scalar()
        if row is None and stage.strip().isdigit():
            return int(stage.strip())
        return row


# Repositories are stateless -- one shared instance is fine.
founder_repository = FounderRepository()
