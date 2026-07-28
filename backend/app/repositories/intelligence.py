"""Founder Intelligence Database (#13) -- read/aggregate access.

Founder-scoped queries over the accumulating dataset: `founder_reports`,
`detected_root_causes`, and `sessions`. Every method filters by `founder_id`, so
one founder can never read another's intelligence.

This is a cross-table read/aggregate repository, so it does not subclass
`BaseRepository` (which is single-model CRUD). It only reads and never commits --
transaction ownership stays with the request session.
"""

from collections.abc import Iterable

from sqlalchemy import Select, case, desc, func, select
from sqlalchemy.orm import Session

from app.models import (
    DetectedRootCause,
    DiagnosisSession,
    FounderReport,
    Intervention,
    RootCause,
    SessionStatus,
)


class IntelligenceRepository:
    # --- reports -----------------------------------------------------------

    def _reports_base(
        self,
        founder_id: int,
        *,
        active_only: bool,
        report_type: str | None,
    ) -> Select:
        stmt = select(FounderReport).where(FounderReport.founder_id == founder_id)
        if active_only:
            stmt = stmt.where(FounderReport.is_active.is_(True))
        if report_type is not None:
            stmt = stmt.where(FounderReport.report_type == report_type)
        return stmt

    def list_reports(
        self,
        db: Session,
        founder_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = False,
        report_type: str | None = None,
    ) -> tuple[list[FounderReport], int]:
        """Report history (newest first) plus the total matching count."""
        base = self._reports_base(
            founder_id, active_only=active_only, report_type=report_type
        )
        total = db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
        rows = list(
            db.execute(
                base.order_by(FounderReport.generated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return rows, total

    def get_report(
        self, db: Session, founder_id: int, report_id: int
    ) -> FounderReport | None:
        """A single report, but only if it belongs to this founder."""
        stmt = select(FounderReport).where(
            FounderReport.report_id == report_id,
            FounderReport.founder_id == founder_id,
        )
        return db.execute(stmt).scalars().first()

    def get_latest_active_report(
        self, db: Session, founder_id: int
    ) -> FounderReport | None:
        stmt = (
            select(FounderReport)
            .where(
                FounderReport.founder_id == founder_id,
                FounderReport.is_active.is_(True),
            )
            .order_by(FounderReport.generated_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalars().first()

    # --- detected root causes (accumulating findings) ----------------------

    def list_detections(
        self,
        db: Session,
        founder_id: int,
        *,
        session_id: int | None = None,
        top_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DetectedRootCause], int]:
        stmt = select(DetectedRootCause).where(
            DetectedRootCause.founder_id == founder_id
        )
        if session_id is not None:
            stmt = stmt.where(DetectedRootCause.session_id == session_id)
        if top_only:
            stmt = stmt.where(DetectedRootCause.is_top_finding.is_(True))

        total = db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        rows = list(
            db.execute(
                stmt.order_by(
                    DetectedRootCause.session_id.desc(),
                    DetectedRootCause.rank.asc(),
                    DetectedRootCause.final_weighted_score.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return rows, total

    # --- label resolution --------------------------------------------------

    def root_cause_labels(
        self, db: Session, ids: Iterable[int]
    ) -> dict[int, tuple[str | None, str | None]]:
        """{root_cause_id: (name, category)} for the given ids."""
        id_list = [int(i) for i in ids]
        if not id_list:
            return {}
        stmt = select(
            RootCause.root_cause_id,
            RootCause.root_cause_name,
            RootCause.root_cause_category,
        ).where(RootCause.root_cause_id.in_(id_list))
        return {row[0]: (row[1], row[2]) for row in db.execute(stmt).all()}

    def intervention_labels(
        self, db: Session, ids: Iterable[int]
    ) -> dict[int, str | None]:
        """{intervention_id: intervention_code} for the given ids."""
        id_list = [int(i) for i in ids]
        if not id_list:
            return {}
        stmt = select(
            Intervention.intervention_id, Intervention.intervention_code
        ).where(Intervention.intervention_id.in_(id_list))
        return {row[0]: row[1] for row in db.execute(stmt).all()}

    # --- accumulating summary ---------------------------------------------

    def confidence_trend(
        self, db: Session, founder_id: int
    ) -> list[DiagnosisSession]:
        """Completed sessions oldest-first -- the confidence/distress trend."""
        stmt = (
            select(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.status == SessionStatus.COMPLETED,
            )
            .order_by(DiagnosisSession.completed_at.asc().nulls_last())
        )
        return list(db.execute(stmt).scalars().all())

    def completed_session_count(self, db: Session, founder_id: int) -> int:
        stmt = select(func.count()).where(
            DiagnosisSession.founder_id == founder_id,
            DiagnosisSession.status == SessionStatus.COMPLETED,
        )
        return db.execute(stmt).scalar_one()

    def distress_session_count(self, db: Session, founder_id: int) -> int:
        stmt = select(func.count()).where(
            DiagnosisSession.founder_id == founder_id,
            DiagnosisSession.distress_mode_triggered.is_(True),
        )
        return db.execute(stmt).scalar_one()

    def report_count(self, db: Session, founder_id: int) -> int:
        stmt = select(func.count()).where(FounderReport.founder_id == founder_id)
        return db.execute(stmt).scalar_one()

    def recurring_root_causes(
        self, db: Session, founder_id: int, *, limit: int = 10
    ) -> list[dict]:
        """Root causes detected across the founder's sessions, most-frequent first.

        Aggregates every detection (across all sessions) by root cause: how often
        it was detected, how often it was a top finding, and its best weighted
        score. This is the core of the accumulating dataset -- patterns that only
        emerge once a founder has more than one session.
        """
        top_sum = func.sum(
            case((DetectedRootCause.is_top_finding.is_(True), 1), else_=0)
        )
        stmt = (
            select(
                DetectedRootCause.root_cause_id,
                func.count().label("occurrences"),
                top_sum.label("times_top_finding"),
                func.max(DetectedRootCause.final_weighted_score).label("best_score"),
            )
            .where(DetectedRootCause.founder_id == founder_id)
            .group_by(DetectedRootCause.root_cause_id)
            .order_by(desc("occurrences"), desc("best_score"))
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        if not rows:
            return []

        labels = self.root_cause_labels(db, (r[0] for r in rows))
        result: list[dict] = []
        for root_cause_id, occurrences, times_top, best in rows:
            name, category = labels.get(root_cause_id, (None, None))
            result.append(
                {
                    "root_cause_id": root_cause_id,
                    "name": name,
                    "category": category,
                    "occurrences": int(occurrences),
                    "times_top_finding": int(times_top or 0),
                    "best_final_weighted_score": best,
                }
            )
        return result


intelligence_repository = IntelligenceRepository()
