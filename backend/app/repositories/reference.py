"""Reference/catalog data access.

Read-only lookups over the seeded catalog tables (founder_stages, industries,
readiness_pillars). No founder data, no commits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import FounderStages, Industries, ReadinessPillars


class ReferenceRepository:
    def stages(self, db: Session) -> list[FounderStages]:
        return list(
            db.execute(select(FounderStages).order_by(FounderStages.stage_order))
            .scalars()
            .all()
        )

    def industries(self, db: Session) -> list[Industries]:
        return list(
            db.execute(select(Industries).order_by(Industries.industry_id))
            .scalars()
            .all()
        )

    def pillars(self, db: Session) -> list[ReadinessPillars]:
        return list(
            db.execute(select(ReadinessPillars).order_by(ReadinessPillars.pillar_id))
            .scalars()
            .all()
        )


reference_repository = ReferenceRepository()
