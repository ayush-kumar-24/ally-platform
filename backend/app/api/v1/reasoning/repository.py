"""Database access for the reasoning layer.

Queries only -- no business rules, no commits (the service owns the transaction).
Reads the reference tables and scoring configuration the engines need, and
persists the pipeline's output (detected_root_causes, founder_reports).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AgentInterpretation,
    Answer,
    DetectedRootCause,
    DiagnosisSession,
    FounderReport,
    FounderStage,
    Industry,
    InternalIntelligenceReport,
    Intervention,
    Problem,
    Question,
    RootCause,
    RootCauseWeight,
    ScoringRule,
    StageDiagnosisLogic,
)


class ReasoningRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Configuration -----------------------------------------------------

    def get_active_rule_values(self) -> dict[str, Decimal]:
        """rule_code -> rule_value for every active scoring rule. This is the raw
        input the configuration layer parses into typed config objects."""
        stmt = select(ScoringRule.rule_code, ScoringRule.rule_value).where(
            ScoringRule.is_active.is_(True)
        )
        return {code: value for code, value in self.db.execute(stmt).all()}

    # --- Session inputs ----------------------------------------------------

    def get_session(self, session_id: int) -> DiagnosisSession | None:
        return self.db.get(DiagnosisSession, session_id)

    def get_session_for_update(self, session_id: int) -> DiagnosisSession | None:
        """Row-lock the session for the persist transaction so concurrent
        completions serialise -- the basis of exactly-once processing."""
        stmt = (
            select(DiagnosisSession)
            .where(DiagnosisSession.session_id == session_id)
            .with_for_update()
        )
        return self.db.execute(stmt).scalars().first()

    def get_active_report(self, session_id: int) -> FounderReport | None:
        """The current active report for a session, if any. Its presence is the
        idempotency signal that reasoning already ran (writes are one atomic
        transaction, so a report exists only on a fully-completed run)."""
        stmt = (
            select(FounderReport)
            .where(
                FounderReport.session_id == session_id,
                FounderReport.is_active.is_(True),
            )
            .order_by(FounderReport.generated_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def get_answers_for_session(self, session_id: int) -> list[Answer]:
        stmt = (
            select(Answer)
            .where(Answer.session_id == session_id)
            .order_by(Answer.answered_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_questions_by_ids(self, question_ids: Iterable[int]) -> dict[int, Question]:
        ids = list(set(question_ids))
        if not ids:
            return {}
        stmt = select(Question).where(Question.question_id.in_(ids))
        return {q.question_id: q for q in self.db.execute(stmt).scalars().all()}

    # --- Reference data (read-only) ---------------------------------------

    def get_root_causes_by_ids(self, root_cause_ids: Iterable[int]) -> dict[int, RootCause]:
        ids = list(set(root_cause_ids))
        if not ids:
            return {}
        stmt = select(RootCause).where(RootCause.root_cause_id.in_(ids))
        return {rc.root_cause_id: rc for rc in self.db.execute(stmt).scalars().all()}

    def get_problems_by_ids(self, problem_ids: Iterable[int]) -> dict[int, Problem]:
        ids = list(set(problem_ids))
        if not ids:
            return {}
        stmt = select(Problem).where(Problem.problem_id.in_(ids))
        return {p.problem_id: p for p in self.db.execute(stmt).scalars().all()}

    def get_founder_stage(self, stage_id: int) -> FounderStage | None:
        return self.db.get(FounderStage, stage_id)

    def get_stage_weights(self, stage_id: int) -> dict[int, Decimal]:
        """root_cause_id -> stage_weight for one stage (the stage-probability
        prior). One query instead of per-cause lookups to avoid N+1."""
        stmt = select(RootCauseWeight.root_cause_id, RootCauseWeight.stage_weight).where(
            RootCauseWeight.stage_id == stage_id
        )
        return {rc_id: weight for rc_id, weight in self.db.execute(stmt).all()}

    def get_industry(self, industry_id: int) -> Industry | None:
        return self.db.get(Industry, industry_id)

    def get_interpretations_by_category(self, category: str) -> list[AgentInterpretation]:
        stmt = select(AgentInterpretation).where(
            AgentInterpretation.category == category
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_stage_logic_for_group(self, stage_group: str) -> list[StageDiagnosisLogic]:
        stmt = (
            select(StageDiagnosisLogic)
            .where(StageDiagnosisLogic.stage_group == stage_group)
            .order_by(StageDiagnosisLogic.display_order.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_interventions_by_ids(
        self, intervention_ids: Iterable[int]
    ) -> dict[int, Intervention]:
        ids = list(set(intervention_ids))
        if not ids:
            return {}
        stmt = select(Intervention).where(Intervention.intervention_id.in_(ids))
        return {i.intervention_id: i for i in self.db.execute(stmt).scalars().all()}

    def get_interventions_by_root_cause_codes(
        self, root_cause_codes: Sequence[str]
    ) -> list[Intervention]:
        """Interventions whose `root_cause_ids` jsonb array contains any of the
        given root-cause CODES, via the Postgres @> containment operator.

        Note the column name is `root_cause_ids` but it stores codes ("RC-001"),
        not integer ids -- matching must go through root_causes.root_cause_code.
        """
        codes = [c for c in set(root_cause_codes) if c]
        if not codes:
            return []
        conditions = [
            Intervention.root_cause_ids.op("@>")(func.jsonb_build_array(code))
            for code in codes
        ]
        stmt = select(Intervention).where(or_(*conditions))
        return list(self.db.execute(stmt).scalars().all())

    # --- Output (writes; flush only) --------------------------------------

    def replace_detected_root_causes(
        self, session_id: int, rows: Iterable[DetectedRootCause]
    ) -> list[DetectedRootCause]:
        """Delete any prior detections for the session and insert the new set.

        Idempotent re-analysis: a session analysed twice ends with exactly one
        set of detections, not duplicates. Flush so ids populate; the service
        commits.
        """
        self.db.execute(
            delete(DetectedRootCause).where(DetectedRootCause.session_id == session_id)
        )
        new_rows = list(rows)
        if new_rows:
            self.db.add_all(new_rows)
            self.db.flush()
        return new_rows

    def add_report(self, report: FounderReport) -> FounderReport:
        self.db.add(report)
        self.db.flush()
        return report

    def replace_internal_report(
        self, session_id: int, report: InternalIntelligenceReport
    ) -> InternalIntelligenceReport:
        """Delete any prior internal report for the session and insert the new
        one. The table has no is_active flag, so re-analysis replaces by deletion
        to stay idempotent (one internal report per session)."""
        self.db.execute(
            delete(InternalIntelligenceReport).where(
                InternalIntelligenceReport.session_id == session_id
            )
        )
        self.db.add(report)
        self.db.flush()
        return report

    def deactivate_existing_reports(self, session_id: int) -> None:
        """Mark prior reports for the session inactive so only the latest is
        current. Uses is_active rather than deletion to preserve history."""
        stmt = (
            select(FounderReport)
            .where(
                FounderReport.session_id == session_id,
                FounderReport.is_active.is_(True),
            )
        )
        for report in self.db.execute(stmt).scalars().all():
            report.is_active = False
