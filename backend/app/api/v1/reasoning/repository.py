"""Database access for the reasoning layer.

Queries only -- no business rules, no commits (the service owns the transaction).
Reads the reference tables and scoring configuration the engines need, and
persists the pipeline's output (detected_root_causes, founder_reports).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.schema import Archetypes, BehaviourPatterns, BlindSpots
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
from app.models.schema import ReadinessPillars


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

    def get_readiness_pillars(self) -> list[ReadinessPillars]:
        """All readiness pillars, ordered. Source of the Business Health Score's
        weights, score bands and red-flag thresholds -- never hardcoded."""
        stmt = select(ReadinessPillars).order_by(ReadinessPillars.pillar_order.asc())
        return list(self.db.execute(stmt).scalars().all())

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

    # --- Overall-confidence inputs ----------------------------------------

    def get_in_scope_question_count(self, stage_id: int | None) -> int:
        """Count of questions in scope for the founder's stage group -- the
        denominator of the confidence EVIDENCE COVERAGE signal.

        A question is in scope when its `primary_stage_group` matches the founder's
        stage group, i.e. the `onboarding_label` of the founder's stage
        (founder_stages: stage_id -> onboarding_label; questions.primary_stage_group
        holds the same group labels 'Stage 0' / 'Stage 0->1' / 'Stage 1->10+').
        Returns 0 when the stage is unknown, so the caller yields 0 coverage rather
        than dividing by zero.
        """
        if stage_id is None:
            return 0
        stmt = (
            select(func.count(Question.question_id))
            .select_from(Question)
            .join(FounderStage, FounderStage.onboarding_label == Question.primary_stage_group)
            .where(FounderStage.stage_id == stage_id)
        )
        return int(self.db.execute(stmt).scalar_one())

    def get_reliability_factor(self, distress_score: Decimal | int | None) -> Decimal | None:
        """session_state_bands.reliability_factor for the band whose score range
        contains the session's distress score -- the confidence RELIABILITY modifier.

        None means either no band matched or the matching band has no factor (the
        High Distress band, 36+, deliberately carries a null factor). Read via a
        Core query because session_state_bands has no ORM model in schema.py.
        """
        if distress_score is None:
            return None
        row = self.db.execute(
            text(
                "select reliability_factor from session_state_bands "
                "where score_min <= :s and (score_max is null or :s <= score_max) "
                "order by score_min desc limit 1"
            ),
            {"s": distress_score},
        ).first()
        return row[0] if row and row[0] is not None else None

    def get_archetypes(self) -> list["Archetypes"]:
        """The seeded founder-archetype catalogue (8 rows) the Archetype engine
        matches a founder against."""
        return list(
            self.db.execute(select(Archetypes).order_by(Archetypes.archetype_id))
            .scalars()
            .all()
        )

    def get_distress_signal_weights(self) -> dict[int, Decimal]:
        """{signal_id: score_per_instance} for every psychological_state_signal.

        The scoring table the Psychological State engine sums over. Core query
        because psychological_state_signals has no ORM model in schema.py."""
        rows = self.db.execute(
            text(
                "select signal_id, score_per_instance from psychological_state_signals "
                "where is_active is true"
            )
        ).all()
        return {int(r[0]): Decimal(r[1]) for r in rows if r[1] is not None}

    def get_distress_signals_catalog(self) -> list[dict]:
        """The full active psychological_state_signals catalogue for the LLM
        language detector: id, state, type, observable indicator, example phrases,
        and per-instance score. Ordered by signal_id for a stable prompt."""
        rows = self.db.execute(
            text(
                "select signal_id, state_code, signal_type, observable_indicator, "
                "example_phrases, score_per_instance from psychological_state_signals "
                "where is_active is true order by signal_id"
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    def get_empathy_protocol(self, prompt_code: str) -> str | None:
        """The distress empathy-protocol text from prompt_library (category
        'distress') for a State A/B/C/D protocol code. None if unseeded/inactive."""
        row = self.db.execute(
            text(
                "select prompt_text from prompt_library "
                "where prompt_code = :c and category = 'distress' and is_active is true"
            ),
            {"c": prompt_code},
        ).first()
        return row[0] if row else None

    def get_acute_distress_signal_id(self) -> int | None:
        """The lowest-severity acute (State D) signal id -- the conservative unit
        the deterministic distress fallback counts in. None if State D is unseeded."""
        row = self.db.execute(
            text(
                "select signal_id from psychological_state_signals "
                "where state_code = 'D' and is_active is true "
                "order by score_per_instance asc, signal_id asc limit 1"
            )
        ).first()
        return int(row[0]) if row else None

    def get_stage_order(self, stage_id: int | None) -> int | None:
        """The ordinal position (founder_stages.stage_order) of a stage, used to
        measure how many stages apart two stages are for the severe-stage-mismatch
        hard rule. None when the stage is unknown."""
        if stage_id is None:
            return None
        stage = self.db.get(FounderStage, stage_id)
        return stage.stage_order if stage is not None else None

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

    def get_blind_spot_ids_by_root_cause_codes(
        self, root_cause_codes: Sequence[str]
    ) -> list[int]:
        """blind_spots whose `linked_root_cause_ids` jsonb array contains any of
        the given root-cause CODES -- same @> containment and same code-not-id
        convention as `get_interventions_by_root_cause_codes` above, confirmed
        against live data (blind_spots.linked_root_cause_ids holds "RC-019"
        style codes, not integer ids).

        Was always skipped by the reasoning report (internal_intelligence_
        reports.blind_spot_ids stayed `[]` for every session) -- not because
        blind_spots has no data (20 real seeded rows), but because nothing ever
        queried it. AllyContext.blind_spot_ids and the knowledge graph's
        *_TO_BLIND_SPOT edges already read this column; they were just always
        empty upstream.
        """
        codes = [c for c in set(root_cause_codes) if c]
        if not codes:
            return []
        conditions = [
            BlindSpots.linked_root_cause_ids.op("@>")(func.jsonb_build_array(code))
            for code in codes
        ]
        stmt = select(BlindSpots.blind_spot_id).where(or_(*conditions))
        return [row[0] for row in self.db.execute(stmt).all()]

    def get_behaviour_pattern_ids_by_root_cause_codes(
        self, root_cause_codes: Sequence[str]
    ) -> list[int]:
        """behaviour_patterns whose `linked_root_cause_ids` jsonb array contains
        any of the given root-cause CODES. Same convention and same "seeded but
        never queried" history as blind_spots above (27 real seeded rows)."""
        codes = [c for c in set(root_cause_codes) if c]
        if not codes:
            return []
        conditions = [
            BehaviourPatterns.linked_root_cause_ids.op("@>")(func.jsonb_build_array(code))
            for code in codes
        ]
        stmt = select(BehaviourPatterns.pattern_id).where(or_(*conditions))
        return [row[0] for row in self.db.execute(stmt).all()]

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
