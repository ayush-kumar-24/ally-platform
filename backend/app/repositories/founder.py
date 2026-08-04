"""Founder repository -- the one concrete example wired into a live route.

Shows the pattern: subclass BaseRepository, add only the model-specific lookups.
Other models get their own repository the same way as features need them.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Founder
from app.repositories.base import BaseRepository
from app.services.profile_progress import validate_profile


class FounderRepository(BaseRepository[Founder]):
    def __init__(self) -> None:
        super().__init__(Founder)

    def update(self, db: Session, obj: Founder, data: dict[str, Any], *, commit: bool = True) -> Founder:
        """Partial update, plus keeping `profile_completed` truthful.

        Nothing else in the codebase ever set this column to true -- it is the
        DB default (false) forever, even once a founder has genuinely filled
        every required onboarding field, because `/profile/validate` computes
        completeness fresh on every call but never persists the result. That
        left `profile_completed` permanently false for every founder, which
        matters beyond just this column: it is the one signal that could tell
        a returning, already-onboarded founder apart from a brand-new one.
        Recomputing it here, on every write through this repository (which is
        every PATCH /profile/* endpoint), means it can never go stale.
        """
        obj = super().update(db, obj, data, commit=False)
        completed = validate_profile(obj)["valid"]
        if obj.profile_completed != completed:
            obj.profile_completed = completed
        self._finish(db, obj, commit)
        return obj

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
