"""Read-only database access for the Ally context layer.

Every method is a SELECT against a FROZEN diagnosis table. No writes, no
recomputation. This is the only place the context layer touches the database, so
the read surface is explicit and auditable.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DetectedRootCause,
    DiagnosisSession,
    Founder,
    FounderReport,
    FounderStage,
    Industry,
    InternalIntelligenceReport,
    RootCause,
)


class AllyContextRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_founder(self, founder_id: int) -> Founder | None:
        return self.db.get(Founder, founder_id)

    def get_stage(self, stage_id: int | None) -> FounderStage | None:
        return self.db.get(FounderStage, stage_id) if stage_id is not None else None

    def get_industry(self, industry_id: int | None) -> Industry | None:
        return self.db.get(Industry, industry_id) if industry_id is not None else None

    def get_session(self, session_id: int | None) -> DiagnosisSession | None:
        return self.db.get(DiagnosisSession, session_id) if session_id is not None else None

    def get_latest_active_report(
        self, founder_id: int, session_id: int | None = None
    ) -> FounderReport | None:
        """The current active founder report -- for a specific session when given,
        otherwise the founder's most recent. Active + newest-first mirrors how the
        reasoning service marks exactly one report current per session."""
        stmt = select(FounderReport).where(
            FounderReport.founder_id == founder_id,
            FounderReport.is_active.is_(True),
        )
        if session_id is not None:
            stmt = stmt.where(FounderReport.session_id == session_id)
        stmt = stmt.order_by(FounderReport.generated_at.desc()).limit(1)
        return self.db.execute(stmt).scalars().first()

    def get_detected_root_causes(self, session_id: int) -> list[DetectedRootCause]:
        stmt = (
            select(DetectedRootCause)
            .where(DetectedRootCause.session_id == session_id)
            .order_by(DetectedRootCause.rank.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_root_causes_by_ids(self, ids: Iterable[int]) -> dict[int, RootCause]:
        id_list = list({i for i in ids})
        if not id_list:
            return {}
        stmt = select(RootCause).where(RootCause.root_cause_id.in_(id_list))
        return {rc.root_cause_id: rc for rc in self.db.execute(stmt).scalars().all()}

    def get_internal_report(self, session_id: int) -> InternalIntelligenceReport | None:
        stmt = (
            select(InternalIntelligenceReport)
            .where(InternalIntelligenceReport.session_id == session_id)
            .order_by(InternalIntelligenceReport.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()
