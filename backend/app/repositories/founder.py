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

        `industry_mapped_id` is kept in step with `industry` for the same
        reason and at the same level. Two endpoints write the industry name --
        PATCH /profile/business and the generic PATCH /profile -- so resolving
        the link in either one of them would let the two columns drift apart
        depending on which door the founder came through. Here, there is only
        one door. Clearing the name clears the link, since a stale FK would
        keep feeding the diagnosis an industry the founder has removed.
        """
        if "industry" in data:
            data = {**data, "industry_mapped_id": self.resolve_industry_id(db, data["industry"])}
        obj = super().update(db, obj, data, commit=False)
        completed = validate_profile(obj)["valid"]
        if obj.profile_completed != completed:
            obj.profile_completed = completed
        self._finish(db, obj, commit)
        return obj

    def get_by_user_id(self, db: Session, user_id) -> Founder | None:
        """Look up a founder by the canonical Ally user UUID."""
        return self.get_by(db, user_id=user_id)

    def get_by_cognito_sub(self, db: Session, cognito_sub: str) -> Founder | None:
        """Look up a founder already linked to an Amazon Cognito identity."""
        return self.get_by(db, cognito_sub=cognito_sub)

    def get_by_email(self, db: Session, email: str) -> Founder | None:
        """Look up a founder by email during one-time Cognito migration linking."""
        return self.get_by(db, email=email)

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

    def resolve_industry_id(self, db: Session, industry: str) -> int | None:
        """Turn an industry name ('BFSI / FinTech') into an industries.industry_id.

        The counterpart of resolve_stage_id, and it exists for the same reason:
        onboarding sends the founder-facing name and the diagnosis reads the id.

        `founders.industry` (free text) and `founders.industry_mapped_id` (the
        FK) have coexisted since the table was written, and NOTHING has ever
        written the FK -- the only code that could was an RDS function
        (complete_onboarding) the application stopped calling. So it has been
        NULL for every founder, while the diagnosis engine, the reasoning
        service and the Ally context builder all read it to choose an
        industry's dataset. Thirty industries' worth of seeded problems, root
        causes, question banks and interventions were therefore unreachable,
        and every founder got the generic bank.

        Matching is on industry_name, which is exactly what the onboarding
        dropdown now stores (see the industry question in
        data/onboardingQuestions.js -- its values are these names character for
        character). industry_code is accepted too so an API client that knows
        the short code is not forced to send prose.

        Returns None when nothing matches, which is the honest answer for
        'Other' and for the free-text industries founders were storing before
        the dropdown was aligned. The caller leaves the FK alone in that case
        rather than guessing.
        """
        return db.execute(
            text(
                "SELECT industry_id FROM industries "
                "WHERE lower(industry_name) = lower(btrim(:s)) "
                "   OR lower(industry_code) = lower(btrim(:s)) "
                "ORDER BY industry_id LIMIT 1"
            ),
            {"s": industry},
        ).scalar()


# Repositories are stateless -- one shared instance is fine.
founder_repository = FounderRepository()
