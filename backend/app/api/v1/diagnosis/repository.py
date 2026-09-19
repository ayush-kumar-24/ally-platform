"""Database access for the diagnosis module.

This layer only builds and runs queries. It holds no business rules, raises no
domain errors, and never commits -- transaction boundaries belong to the
service so that a single request stays atomic.
"""

from datetime import datetime
from typing import Iterable

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text as _text
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models import (
    Answer,
    CapabilityEvidence,
    DiagnosisSession,
    Question,
    SessionStatus,
)
from app.models.enums import ScoreLabel
from app.models.schema import FounderDnaAnswers, FounderDnaQuestions
from app.models.session_context import SessionContextFact


class DiagnosisRepository:
    def __init__(self, db: Session):
        self.db = db
        #: Request-lifetime cache for problem_to_pillar() -- see its docstring.
        self._problem_to_pillar: dict[int, int] | None = None
        #: Same, for problem_to_dimension().
        self._problem_to_dimension: dict[int, str] | None = None
        #: Same, for problem_to_code().
        self._problem_to_code: dict[int, str] | None = None
        #: Same, for root_cause_to_code().
        self._root_cause_to_code: dict[int, str] | None = None

    # --- Sessions ---

    def lock_founder_for_diagnosis_start(self, founder_id: int) -> None:
        """Row-level lock, held for the rest of this transaction.

        Live-reproduced: two near-simultaneous POST /diagnosis/start calls for
        the same founder both read "no active session, 0 used this month"
        before either had committed, so both passed the monthly limit check
        and both created an in-progress session -- a limit of 1 became 2, and
        the "never fork the assessment" invariant start_session's own
        docstring describes was violated. SELECT ... FOR UPDATE here blocks a
        concurrent second call until the first one's transaction resolves, at
        which point it correctly sees the just-created session and takes the
        resume path instead of creating a duplicate. Scoped to one founder's
        row -- does not serialize unrelated founders against each other.
        """
        self.db.execute(
            _text("select founder_id from founders where founder_id = :f for update"),
            {"f": founder_id},
        )

    def lock_session_for_update(self, session_id: int) -> None:
        """Row-level lock on one session, held for the rest of this transaction.

        Taken immediately before submit_answer's progress-update commit, NOT at
        the top of the request: everything above that point is the two LLM calls,
        and holding a transaction open across them is the exact failure the
        two-commit split in submit_answer exists to avoid (Supabase's pooler
        closes a connection left idle-in-transaction for tens of seconds).

        What it protects: two concurrent answers to the same question -- a
        double-click, or a client retry that overlapped the original -- both
        reached the progress update with independently chosen next questions.
        The unique index on answers stops the duplicate row, but nothing stopped
        the second request overwriting the first's current_question_id, so the
        founder's next submission 409'd against a question they were never
        shown. With this lock the loser blocks here, then sees the pointer has
        already moved and declines to clobber it.
        """
        self.db.execute(
            _text("select session_id from sessions where session_id = :s for update"),
            {"s": session_id},
        )

    def get_session_by_id(self, session_id: int) -> DiagnosisSession | None:
        return self.db.get(DiagnosisSession, session_id)

    def get_detected_root_cause_ids(self, session_id: int) -> set[int]:
        """Root causes this session has already detected.

        Drives the validate-mode question bias: once there are candidate causes,
        questions that could confirm or rule one out are worth more than another
        broad sweep. Empty until the reasoning pipeline has written detections.
        """
        rows = self.db.execute(
            _text("select root_cause_id from detected_root_causes where session_id = :s"),
            {"s": session_id},
        ).scalars().all()
        return {int(r) for r in rows if r is not None}

    def count_sessions_started_since(self, founder_id: int, since: datetime) -> int:
        """Diagnoses this founder has STARTED since `since`, whatever their state.

        Counts abandoned and completed runs alike: the cost of a diagnosis is
        incurred when it is started and questions are answered, not when it is
        finished, so counting only completions would let someone abandon at
        question 29 and start again for free.
        """
        return self.db.scalar(
            select(func.count())
            .select_from(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.started_at >= since,
            )
        ) or 0

    def count_completed_sessions(self, founder_id: int) -> int:
        """Diagnoses this founder has ever COMPLETED -- a lifetime count, not
        scoped to a month.

        Backs the lifetime diagnosis cap: an abandoned or still-in-progress
        session must never count here, because the resume path must never be
        blocked and a founder must never be told their one free diagnosis is
        "used" before they have actually reached a report.
        """
        return self.db.scalar(
            select(func.count())
            .select_from(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.status == SessionStatus.COMPLETED,
            )
        ) or 0

    def get_active_session_for_founder(self, founder_id: int) -> DiagnosisSession | None:
        """Most recent in-progress session, if any.

        Ordered newest-first so that historical data predating the
        one-active-session rule still resolves deterministically.
        """
        stmt = (
            select(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.status == SessionStatus.IN_PROGRESS,
            )
            .order_by(DiagnosisSession.started_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def add_session(self, session: DiagnosisSession) -> DiagnosisSession:
        """Stage a new session and flush so `session_id` is populated.

        Flush, not commit: the caller may still need to attach the first
        question in the same transaction.
        """
        self.db.add(session)
        self.db.flush()
        return session

    # --- Questions ---

    def get_question_by_id(self, question_id: int) -> Question | None:
        return self.db.get(Question, question_id)

    def get_answered_question_ids(self, session_id: int) -> set[int]:
        stmt = select(Answer.question_id).where(Answer.session_id == session_id)
        return set(self.db.execute(stmt).scalars().all())

    def count_scored_answers(self, session_id: int) -> int:
        """Answers that carry diagnostic weight -- NOT_APPLICABLE excluded.

        `questions_answered_count` counts every answer row, because it also
        meters the question BUDGET and an N/A question was still asked. Coverage
        and completion are a different question: "how much do we know", not "how
        many turns have we spent". An N/A answer establishes nothing about the
        business, so counting it there lets a founder whose questions mostly did
        not apply cross the completion threshold on empty evidence.

        NULL counts as scored. A row is NULL-labelled when classification failed
        or has not run, which is an unmeasured answer rather than an inapplicable
        one -- treating it as N/A would quietly shrink coverage every time the
        classifier erred.
        """
        stmt = select(func.count()).select_from(Answer).where(
            Answer.session_id == session_id,
            func.coalesce(Answer.score_label, "") != ScoreLabel.NOT_APPLICABLE.value,
        )
        return int(self.db.execute(stmt).scalar() or 0)

    # --- Target-state knowledge base ---------------------------------------

    def capability_requirement_rows(self) -> list:
        """Every capability_requirements row, joined to its capability code.

        Returned WHOLE and unfiltered on purpose. The table is curated reference
        data -- 54 rows today, a few hundred at most -- and the specificity
        cascade is easier to read, test and explain in one Python function than
        as a window query nobody dares change. Filtering here would also split
        the rule across two places, which is how the two stop agreeing.

        Returns [] when the table does not exist -- any database that has not
        run a8d34f7e2b91 -- so a caller degrades to "no requirements" rather
        than raising. Same fail-open as every other optional map in this module.
        """
        sql = (
            "SELECT r.requirement_id, r.capability_id, c.capability_code,"
            "       r.industry_code, r.business_model, r.from_stage_order,"
            "       r.target_revenue_band, r.target_time_horizon,"
            "       r.required_level, r.necessity, r.rationale"
            "  FROM capability_requirements r"
            "  JOIN capabilities c ON c.capability_id = r.capability_id"
        )
        try:
            return list(self.db.execute(_text(sql)).mappings().all())
        except Exception:                                      # noqa: BLE001
            logger.warning(
                "capability_requirements unavailable; no target-state requirements",
                extra={"stage": "target_state"},
            )
            return []

    # --- Capability evidence -------------------------------------------------

    def capability_and_criteria_for_question(self, question_id: int) -> dict | None:
        """The one capability this question maps to, plus its evidence criteria.

        Returns None when the question is unmapped -- the 1,874 questions Step
        7A left untouched -- which is the caller's signal to attempt no
        extraction at all rather than extracting against nothing.

        `question_capabilities` is Step 7A's invariant: at most one capability
        per question. `LIMIT 1` is a safety net for that invariant, not a design
        choice -- if it ever fired on real data, that would itself be the bug.

        Returns {} (falls back to None-like) when the tables do not exist -- any
        database that has not run Steps 5-7B -- so evidence extraction degrades
        to "off" rather than raising.
        """
        sql = (
            "SELECT c.capability_id, c.capability_code, c.capability_name,"
            "       e.criterion_id, e.criterion_text"
            "  FROM question_capabilities qc"
            "  JOIN capabilities c ON c.capability_id = qc.capability_id"
            "  LEFT JOIN capability_evidence_criteria e"
            "         ON e.capability_id = c.capability_id"
            " WHERE qc.question_id = :qid"
            " ORDER BY e.criterion_order"
        )
        try:
            rows = self.db.execute(_text(sql), {"qid": question_id}).all()
        except Exception:                                       # noqa: BLE001
            logger.warning(
                "capability mapping unavailable; no evidence extraction",
                extra={"stage": "capability_evidence", "question_id": question_id},
            )
            return None
        if not rows:
            return None
        capability_id, capability_code, capability_name = rows[0][:3]
        criteria = [
            {"criterion_id": cid, "criterion_text": ctext}
            for _cap, _code, _name, cid, ctext in rows if cid is not None
        ]
        return {
            "capability_id": capability_id,
            "capability_code": capability_code,
            "capability_name": capability_name,
            "criteria": criteria,
        }

    def record_capability_evidence(
        self,
        *,
        capability_id: int,
        question_id: int,
        answer_id: int,
        observed_level: int,
        confidence: float,
        evidence_text: str,
        criterion_id: int | None = None,
    ) -> bool:
        """Persist one observation. Returns False, not an error, on a repeat.

        `ON CONFLICT (answer_id) DO NOTHING` is the idempotency guard from a
        UNIQUE constraint, not application logic: reprocessing the same answer
        -- a retried request, a replayed webhook -- must never create a second
        observation, and the database refuses it unconditionally rather than
        this method having to notice and skip.

        Does not commit; the caller's transaction boundary owns that, as for
        every other write in this class.
        """
        # `.returning(...)` and a row-count check, NOT `result.rowcount`: SQLAlchemy
        # attaches an implicit RETURNING to an ORM-targeted insert (to populate
        # the identity map), and that makes the DBAPI-level rowcount unreliable
        # with ON CONFLICT DO NOTHING -- verified directly against this driver,
        # where it read -1 on a real, successful insert. Checking whether a row
        # came back is unambiguous regardless of driver rowcount quirks.
        stmt = (
            pg_insert(CapabilityEvidence)
            .values(
                capability_id=capability_id,
                question_id=question_id,
                answer_id=answer_id,
                criterion_id=criterion_id,
                observed_level=observed_level,
                confidence=confidence,
                evidence_text=evidence_text,
            )
            .on_conflict_do_nothing(constraint="uq_capability_evidence_answer")
            .returning(CapabilityEvidence.evidence_id)
        )
        return self.db.execute(stmt).first() is not None

    def capability_evidence_for_session(self, session_id: int) -> list[dict]:
        """Every observation recorded so far in one session. Read-only, for
        debugging and for Step 7C's future aggregation -- not consumed by
        anything in Step 7B itself."""
        sql = (
            "SELECT ev.evidence_id, ev.capability_id, c.capability_code,"
            "       ev.question_id, ev.answer_id, ev.criterion_id,"
            "       ev.observed_level, ev.confidence, ev.evidence_text,"
            "       ev.created_at"
            "  FROM capability_evidence ev"
            "  JOIN capabilities c ON c.capability_id = ev.capability_id"
            "  JOIN answers a ON a.answer_id = ev.answer_id"
            " WHERE a.session_id = :sid"
            " ORDER BY ev.created_at"
        )
        return [dict(r) for r in self.db.execute(_text(sql), {"sid": session_id}).mappings().all()]

    def current_capability_assessments(self, session_id: int):
        """Step 7C: the current read for every capability this session has AT
        LEAST ONE observation for. A thin composition -- read the immutable
        evidence, hand it to the pure aggregator -- deliberately not a new
        query of its own, so the SAME rows `capability_evidence_for_session`
        already exposes for debugging are what the assessment is computed
        from. No new table, no write, no side effect.
        """
        from app.api.v1.diagnosis.capability_assessment import assess_capabilities

        return assess_capabilities(self.capability_evidence_for_session(session_id))

    def capability_names(self) -> dict[int, str]:
        """capability_id -> capability_name, in one bounded query.

        The taxonomy is small and static (34 rows), so this is the whole
        table, not a filtered lookup -- cheaper to fetch once per gap
        computation than to look up per capability, and it is what keeps
        `compute_capability_gaps` from needing a database handle at all.
        """
        sql = "SELECT capability_id, capability_name FROM capabilities"
        try:
            return dict(self.db.execute(_text(sql)).all())
        except Exception:                                      # noqa: BLE001
            logger.warning("capabilities unavailable; gap names will fall back "
                           "to capability_code", extra={"stage": "gap_engine"})
            return {}

    def capability_gaps_for_session(self, session_id: int, founder_context, target):
        """Step 8: FounderContext + TargetStateContext -> tuple[CapabilityGap, ...].

        Composes three ALREADY-BOUNDED reads -- requirement rows, this
        session's assessments, and the capability name map -- and hands them
        to the pure comparison in `gap_engine.py`. No N+1: exactly three
        queries regardless of how many capabilities are relevant, because both
        `capability_requirement_rows` and `capability_names` fetch their whole
        (small, static) table once, and `current_capability_assessments`
        already bounds itself to one session's evidence in one query.

        Neither `resolve_requirements` nor `assess_capabilities` is
        reimplemented here -- this method's only job is fetching their inputs
        and forwarding their outputs to the comparison.
        """
        from app.api.v1.diagnosis.gap_engine import compute_capability_gaps
        from app.api.v1.diagnosis.target_state import resolve_requirements

        requirements = resolve_requirements(
            self.capability_requirement_rows(), founder_context, target
        )
        assessments = self.current_capability_assessments(session_id)
        names = self.capability_names()
        return compute_capability_gaps(requirements, assessments, names)

    def prioritized_capability_gaps_for_session(self, session_id: int, founder_context, target):
        """Step 9A: the same session's `CapabilityGap`s (Step 8, above),
        filtered to `status == GAP` and ordered by `gap_priority.py`'s
        documented, deterministic factors. Adds no query of its own -- it is
        exactly `capability_gaps_for_session`'s output, prioritized."""
        from app.api.v1.diagnosis.gap_priority import prioritize_capability_gaps

        gaps = self.capability_gaps_for_session(session_id, founder_context, target)
        return prioritize_capability_gaps(gaps)

    def stage_id_for_stage_order(self, stage_order: int | None) -> int | None:
        """founder_stages.stage_id for a stage_order, or None when unknown.

        A real lookup, not an assumption: `interventions.stage_relevance` holds
        stage_ids while FounderContext carries a stage_order. The two coincide
        in today's seed data and relying on that coincidence would be a latent
        bug the day a stage is inserted or reordered.
        """
        if stage_order is None:
            return None
        try:
            return self.db.execute(
                _text("SELECT stage_id FROM founder_stages WHERE stage_order = :o"),
                {"o": stage_order},
            ).scalar()
        except Exception:                                      # noqa: BLE001
            logger.warning("founder_stages unavailable; intervention stage filter "
                           "will fail open", extra={"stage": "gap_intervention"})
            return None

    def interventions_for_capabilities(self, capability_ids) -> dict[int, list]:
        """{capability_id: [intervention rows]} for the curated
        `intervention_capabilities` map, in ONE bounded query.

        Read-only, and never N+1 regardless of how many capabilities are gapped:
        the whole set is fetched with a single `= ANY(:ids)`. Rows come back
        ordered by intervention_id so the caller's own ordering starts from a
        stable place. Nothing here filters -- eligibility is the pure
        function's job, against the existing relevance strategy.
        """
        ids = [int(cid) for cid in capability_ids]
        if not ids:
            return {}
        sql = (
            "SELECT ic.capability_id, i.intervention_id, i.intervention_code,"
            "       i.section, i.stage_relevance, i.industry_relevance"
            "  FROM intervention_capabilities ic"
            "  JOIN interventions i ON i.intervention_id = ic.intervention_id"
            " WHERE ic.capability_id = ANY(:ids)"
            " ORDER BY ic.capability_id, i.intervention_id"
        )
        try:
            rows = self.db.execute(_text(sql), {"ids": ids}).mappings().all()
        except Exception:                                      # noqa: BLE001
            logger.warning("intervention_capabilities unavailable; every gap will "
                           "read as uncovered", extra={"stage": "gap_intervention"})
            return {}
        by_capability: dict[int, list] = {}
        for row in rows:
            by_capability.setdefault(row["capability_id"], []).append(dict(row))
        return by_capability

    def intervention_candidates_for_session(self, session_id: int, founder_context, target):
        """Step 9B: this session's prioritized gaps -> existing intervention
        candidates + explicitly uncovered gaps. Read-only; issues no write."""
        from app.api.v1.diagnosis.gap_intervention import select_interventions_for_gaps

        gaps = self.prioritized_capability_gaps_for_session(
            session_id, founder_context, target
        )
        by_capability = self.interventions_for_capabilities(
            tuple(g.capability_id for g in gaps)
        )
        return select_interventions_for_gaps(
            gaps, by_capability,
            stage_id=self.stage_id_for_stage_order(
                getattr(founder_context, "stage_order", None)),
            industry_code=getattr(founder_context, "industry_code", None),
        )

    def capability_detail(self, capability_ids) -> dict[int, dict]:
        """{capability_id: {capability_name, description}} in one bounded query.
        The capability IS the 20-day outcome, so its own words are what the
        target states -- nothing is composed from them."""
        ids = [int(cid) for cid in capability_ids]
        if not ids:
            return {}
        try:
            rows = self.db.execute(_text(
                "SELECT capability_id, capability_code, capability_name, description"
                "  FROM capabilities WHERE capability_id = ANY(:ids)"
            ), {"ids": ids}).mappings().all()
        except Exception:                                      # noqa: BLE001
            logger.warning("capability detail unavailable",
                           extra={"stage": "twenty_day_target"})
            return {}
        return {row["capability_id"]: dict(row) for row in rows}

    def capability_criteria(self, capability_ids) -> dict[int, list]:
        """{capability_id: [evidence criteria]} in one bounded query.

        These are Step 5's criteria, reused verbatim as 20-day success
        criteria. No second evidence taxonomy is created: the criterion_ids
        carried here are the same ones Step 7B cites when it later records
        evidence, which is what lets the loop close.
        """
        ids = [int(cid) for cid in capability_ids]
        if not ids:
            return {}
        try:
            rows = self.db.execute(_text(
                "SELECT capability_id, criterion_id, criterion_order, criterion_text"
                "  FROM capability_evidence_criteria WHERE capability_id = ANY(:ids)"
                " ORDER BY capability_id, criterion_order"
            ), {"ids": ids}).mappings().all()
        except Exception:                                      # noqa: BLE001
            logger.warning("capability criteria unavailable",
                           extra={"stage": "twenty_day_target"})
            return {}
        by_capability: dict[int, list] = {}
        for row in rows:
            by_capability.setdefault(row["capability_id"], []).append(dict(row))
        return by_capability

    def intervention_steps(self, intervention_ids) -> dict[int, list]:
        """{intervention_id: [immediate_next_steps]} in one bounded query.

        Copied verbatim, exactly as the existing recommendation engine already
        copies the same column into `Recommendation.next_actions`. Separate
        from `interventions_for_capabilities` so Step 9B's own query and its
        content-free candidate object stay untouched.
        """
        ids = [int(iid) for iid in intervention_ids]
        if not ids:
            return {}
        try:
            rows = self.db.execute(_text(
                "SELECT intervention_id, immediate_next_steps FROM interventions"
                " WHERE intervention_id = ANY(:ids)"
            ), {"ids": ids}).mappings().all()
        except Exception:                                      # noqa: BLE001
            logger.warning("intervention steps unavailable",
                           extra={"stage": "twenty_day_target"})
            return {}
        return {
            row["intervention_id"]: [str(s) for s in (row["immediate_next_steps"] or [])]
            for row in rows
        }

    def twenty_day_target_for_session(self, session_id: int, founder_context, target,
                                      *, narrator=None):
        """Step 10A: this session's diagnosis -> one 20-day execution target.

        Read-only. Knows nothing about plans, tiers or prices -- entitlement is
        a router concern in this codebase, and all paid plans consume this
        same engine unchanged.
        """
        from app.api.v1.diagnosis.gap_intervention import select_interventions_for_gaps
        from app.api.v1.diagnosis.twenty_day_target import (
            build_twenty_day_target,
            narrate_target,
        )

        gaps = self.prioritized_capability_gaps_for_session(
            session_id, founder_context, target
        )
        capability_ids = tuple(g.capability_id for g in gaps)
        selection = select_interventions_for_gaps(
            gaps, self.interventions_for_capabilities(capability_ids),
            stage_id=self.stage_id_for_stage_order(
                getattr(founder_context, "stage_order", None)),
            industry_code=getattr(founder_context, "industry_code", None),
        )
        result = build_twenty_day_target(
            gaps, selection,
            self.capability_detail(capability_ids),
            self.capability_criteria(capability_ids),
            self.intervention_steps(
                tuple(c.intervention_id for c in selection.candidates)),
        )
        return narrate_target(result, narrator)

    def strategic_direction_for_session(self, session_id: int, founder_context, target,
                                        *, narrator=None):
        """Step 10B: this session's capability state + the founder's destination
        -> an ordered capability trajectory.

        Read-only, and independent of Step 10A: nothing here reads or waits on a
        20-day target. Step 6's ambiguity is CAUGHT and reported rather than
        allowed to abort a founder's diagnosis or be silently guessed past --
        `resolve_requirements` raises for one undecidable capability, which
        would otherwise take the whole direction down with it.
        """
        from app.api.v1.diagnosis.strategic_direction import (
            ambiguous_direction,
            build_strategic_direction,
            narrate_direction,
        )
        from app.api.v1.diagnosis.target_state import (
            AmbiguousRequirementError,
            resolve_requirements,
        )

        try:
            requirements = resolve_requirements(
                self.capability_requirement_rows(), founder_context, target)
            gaps = self.capability_gaps_for_session(session_id, founder_context, target)
        except AmbiguousRequirementError as exc:
            return ambiguous_direction(target, str(exc))

        direction = build_strategic_direction(
            gaps, requirements,
            self.capability_detail(tuple(g.capability_id for g in gaps)),
            target,
        )
        return narrate_direction(direction, narrator)

    def intervention_coverage_summary(self) -> list[dict]:
        """Per-capability intervention coverage, for content-gap analysis.

        Library-wide and founder-independent -- it answers "what can the
        library address at all", not "what does this founder get". One bounded
        query over two small static tables.
        """
        sql = (
            "SELECT c.capability_id, c.capability_code, c.capability_name,"
            "       count(ic.intervention_id) AS mapped"
            "  FROM capabilities c"
            "  LEFT JOIN intervention_capabilities ic"
            "         ON ic.capability_id = c.capability_id"
            " GROUP BY c.capability_id, c.capability_code, c.capability_name"
            " ORDER BY mapped, c.capability_code"
        )
        try:
            return [dict(r) for r in self.db.execute(_text(sql)).mappings().all()]
        except Exception:                                      # noqa: BLE001
            logger.warning("intervention coverage unavailable",
                           extra={"stage": "gap_intervention"})
            return []

    # --- Session-learned context -------------------------------------------

    def session_context_facts(self, session_id: int) -> dict[str, bool]:
        """token -> value for everything THIS session established.

        The shape `FounderContext.with_session_facts` takes. Absent tokens are
        UNKNOWN; there is no third value to read back because "we do not know"
        is never written down.
        """
        stmt = select(SessionContextFact.token, SessionContextFact.value).where(
            SessionContextFact.session_id == session_id
        )
        return {token: bool(value) for token, value in self.db.execute(stmt).all()}

    def record_session_fact(
        self, session_id: int, token: str, value: bool, answer_id: int | None = None
    ) -> None:
        """Upsert one fact. Session-scoped; `founders` is never touched.

        Upsert rather than insert because a later answer about the same subject
        should REPLACE the earlier reading, not sit beside it contradicting it.
        The unique constraint on (session_id, token) is what makes that atomic.

        Does not commit -- transaction boundaries belong to the service, as for
        every other write in this class.
        """
        stmt = (
            pg_insert(SessionContextFact)
            .values(
                session_id=session_id,
                token=token,
                value=value,
                learned_from_answer_id=answer_id,
            )
            .on_conflict_do_update(
                constraint="uq_session_context_facts",
                set_={"value": value, "learned_from_answer_id": answer_id},
            )
        )
        self.db.execute(stmt)

    def precondition_tokens_by_question(
        self, question_ids: Iterable[int] | None = None
    ) -> dict[int, frozenset[str]]:
        """question_id -> the precondition tokens it carries, for tagged rows only.

        Questions with no precondition are ABSENT from the map rather than
        present with an empty set; that is what lets the gate treat a missing
        key as unconditional without a second lookup. 91 of 3,460 rows are in
        here today, so the map is small even unfiltered.

        Returns {} when `question_tags.precondition_token` does not exist -- any
        database that has not run b7c2d94e5f10 -- so the gate degrades to "ask
        everything" rather than raising. Same fail-open as every other optional
        map in this package.
        """
        sql = (
            "SELECT m.question_id, t.precondition_token"
            "  FROM question_tag_mapping m"
            "  JOIN question_tags t ON t.tag_id = m.tag_id"
            " WHERE t.precondition_token IS NOT NULL"
        )
        params: dict = {}
        ids = list(question_ids) if question_ids is not None else None
        if ids is not None:
            if not ids:
                return {}
            sql += " AND m.question_id = ANY(:ids)"
            params["ids"] = ids
        try:
            rows = self.db.execute(_text(sql), params).all()
        except Exception:                                      # noqa: BLE001
            logger.warning(
                "precondition_token unavailable; applicability gate disabled",
                extra={"stage": "applicability"},
            )
            return {}

        out: dict[int, set[str]] = {}
        for question_id, token in rows:
            if token:
                out.setdefault(question_id, set()).add(token.strip())
        return {qid: frozenset(tokens) for qid, tokens in out.items()}

    def list_candidate_questions(
        self,
        session_id: int,
        stage_groups: list[str],
        founder_id: int | None = None,
    ) -> list[Question]:
        """Every question still unanswered in this session and valid for the
        founder's stage.

        A question must be TAGGED for one of the founder's stage groups to be
        eligible. An untagged one (NULL `primary_stage_group`) is not a
        stage-agnostic question that suits everybody -- it is a question nobody
        decided a stage for, and it used to be served to every founder at every
        stage on exactly that basis. That is how a scaling founder gets asked
        an ideation question and an ideation founder gets asked about revenue
        concentration: silently, with no error and nothing in the logs.

        The bank has no such rows today -- all 1,213 seeded questions are
        pinned to exactly one group -- so this changes no founder's diagnosis
        now. It closes the door for the next question added without a tag,
        which would otherwise reach everyone. Migration `b7e4f2a91c58` shuts
        the same door at the database, so an untagged row cannot be inserted in
        the first place; this is the half that protects sessions running
        against a database where that constraint has not been validated yet.

        Note how narrow a single stage group can be before assuming this leaves
        plenty of breadth: Market Clarity had just four questions reachable by a
        scaling founder until
        `f6d2a81c53e7_retag_market_clarity_scaling_questions` moved 134
        mis-tagged ones. Check the real distribution rather than trusting that
        a group is well stocked.

        Ordering is left to the engine -- this returns an unordered candidate
        set on purpose.
        """
        answered = select(Answer.question_id).where(Answer.session_id == session_id)

        stmt: Select = select(Question).where(
            Question.question_id.not_in(answered),
            Question.primary_stage_group.in_(stage_groups),
        )

        # Do not re-ask what Founder DNA already asked.
        #
        # 11 rows in `questions` (all category "Founder Psychology") are
        # word-for-word identical to rows in `founder_dna_questions` -- e.g.
        # q=309 == dna=103 "In one sentence, why does this problem deserve your
        # next few years?". Founder DNA runs BEFORE the diagnosis in the journey,
        # so the founder answers those there and is then asked them again here,
        # verbatim. Observed live: two of one founder's ~30 diagnosis questions
        # were re-runs of answers Ally already had.
        #
        # That is worse than wasted budget. A ~30-question diagnosis spending
        # slots re-collecting known answers is a smaller diagnosis, and to the
        # founder it reads as Ally having forgotten what they just said.
        #
        # Matched on normalised text rather than an id mapping because the two
        # banks have no foreign key between them -- the duplication is literal
        # text, so text is what identifies it. Scoped to answers THIS founder
        # actually gave, so an unanswered Founder DNA question stays available.
        if founder_id is not None:
            already_told_us = (
                select(func.lower(func.trim(FounderDnaQuestions.question_text)))
                .join(
                    FounderDnaAnswers,
                    FounderDnaAnswers.founder_dna_question_id
                    == FounderDnaQuestions.founder_dna_question_id,
                )
                .where(FounderDnaAnswers.founder_id == founder_id)
            )
            stmt = stmt.where(
                func.lower(func.trim(Question.question_text)).not_in(already_told_us)
            )

        return list(self.db.execute(stmt).scalars().all())

    # --- Pillar membership ---
    #
    # An answer belongs to a readiness pillar via
    # question.problem_id -> problems.pillar_id. The Business Health engine
    # already relies on that chain to score; these two methods let the
    # SELECTION side see the same fact, so the engine can spread the question
    # budget across pillars instead of draining whichever category happens to
    # sort first.

    def problem_to_pillar(self) -> dict[int, int]:
        """{problem_id: pillar_id} for the whole catalogue.

        Small (a few hundred rows) and read-only, so it is fetched whole
        rather than joined per candidate -- the candidate set is re-read on
        every question and a join there would repeat this work each time.

        Memoised for the life of this repository, which is one request: the
        problem catalogue is reference data that cannot change mid-request,
        and both select_next_question and order_candidates ask for it. Without
        this each call was a fresh round-trip to fetch identical rows.
        """
        if self._problem_to_pillar is None:
            rows = self.db.execute(
                _text(
                    "select problem_id, pillar_id from problems "
                    "where pillar_id is not null"
                )
            ).all()
            self._problem_to_pillar = {
                problem_id: pillar_id for problem_id, pillar_id in rows
            }
        return self._problem_to_pillar

    def problem_to_dimension(self) -> dict[int, str]:
        """{problem_id: dimension_code} for problems that have one.

        Same shape, size and memoisation rationale as `problem_to_pillar`, and
        deliberately a SEPARATE query rather than a second column on that one:
        the pillar map is complete and load-bearing (an answer with no pillar
        scores nothing), while this map is partial by design and only ever
        narrows scope. Keeping them apart means a caller cannot accidentally
        treat a missing dimension as a missing pillar.

        Problems with a NULL dimension_code are simply absent from the result.
        That is the normal case for most of the catalogue -- Part 2's twenty
        dimensions do not name every family in the bank, and the ones they do
        name mostly need a content pass to assign. See
        `business_dna.CATEGORIES_WITHOUT_A_DIMENSION`.
        """
        if self._problem_to_dimension is None:
            rows = self.db.execute(
                _text(
                    "select problem_id, dimension_code from problems "
                    "where dimension_code is not null"
                )
            ).all()
            self._problem_to_dimension = {
                problem_id: dimension_code for problem_id, dimension_code in rows
            }
        return self._problem_to_dimension

    def problem_to_code(self) -> dict[int, str]:
        """{problem_id: problem_code} for the whole catalogue.

        Same shape, size and memoisation rationale as `problem_to_pillar`, and
        again a separate query rather than another column on it: that map is
        load-bearing for scoring, this one only feeds the context gate
        (`context_scope`), and a caller must not be able to treat a missing
        code as a missing pillar.

        The code is the stable, human-checkable identity of a problem --
        `problem_id` is a surrogate key that migrations have reassigned before,
        so a precondition map keyed on ids would silently point at the wrong
        problems after a reseed. Keying on codes is why that map is reviewable.
        """
        if self._problem_to_code is None:
            rows = self.db.execute(
                _text(
                    "select problem_id, problem_code from problems "
                    "where problem_code is not null"
                )
            ).all()
            self._problem_to_code = {
                problem_id: problem_code for problem_id, problem_code in rows
            }
        return self._problem_to_code

    def root_cause_to_code(self) -> dict[int, str]:
        """{root_cause_id: root_cause_code} for the whole catalogue.

        Same shape and memoisation rationale as `problem_to_code`. Needed
        because the context gate withholds a few root causes that sit under an
        otherwise-unconditional problem (FND-005) -- see
        `context_scope.ROOT_CAUSE_PRECONDITIONS`.
        """
        if self._root_cause_to_code is None:
            rows = self.db.execute(
                _text(
                    "select root_cause_id, root_cause_code from root_causes "
                    "where root_cause_code is not null"
                )
            ).all()
            self._root_cause_to_code = {rid: code for rid, code in rows}
        return self._root_cause_to_code

    def answered_count_per_pillar_category(
        self, session_id: int
    ) -> dict[tuple[int, str], int]:
        """{(pillar_id, category): answered_count} for this session.

        Returned at (pillar, category) grain rather than per-pillar because
        the engine round-robins at both levels: across pillars so all six get
        covered, and across categories WITHIN a pillar so a pillar's score is
        not read off a single narrow slice of it. Per-pillar totals are summed
        from this, so one query serves both.

        The round-robin depends on this counting ANSWERED questions, not asked
        ones: an unanswered question must not consume a pillar's turn, or
        abandoning one question would silently skip that pillar for the rest
        of the session.
        """
        rows = self.db.execute(
            _text(
                "select p.pillar_id, q.category, count(*) "
                "from answers a "
                "join questions q on q.question_id = a.question_id "
                "join problems p on p.problem_id = q.problem_id "
                "where a.session_id = :sid and p.pillar_id is not null "
                "group by p.pillar_id, q.category"
            ),
            {"sid": session_id},
        ).all()
        return {(pillar_id, category): count for pillar_id, category, count in rows}

    # --- Answers ---

    def get_answer(self, session_id: int, question_id: int) -> Answer | None:
        stmt = select(Answer).where(
            Answer.session_id == session_id,
            Answer.question_id == question_id,
        )
        return self.db.execute(stmt).scalars().first()

    def add_answer(self, answer: Answer) -> Answer:
        self.db.add(answer)
        self.db.flush()
        return answer

    def recent_qa(self, session_id: int, limit: int = 5) -> list[tuple[str, str]]:
        """The last `limit` (question_text, answer_text) pairs, oldest-first, for
        adaptive next-question context. Ordered by answer time."""
        stmt = (
            select(Question.question_text, Answer.answer_text)
            .join(Answer, Answer.question_id == Question.question_id)
            .where(Answer.session_id == session_id)
            .order_by(Answer.answered_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [(qt, at) for qt, at in reversed(rows)]

    def full_qa_history(self, session_id: int) -> list[tuple[str, str, str, datetime]]:
        """Every (question_text, category, answer_text, answered_at) this session
        has answered so far, oldest-first, unlike `recent_qa` above which is
        capped for LLM prompt context.

        Live-reproduced gap: reloading the diagnosis page (or resuming after
        closing the tab) showed only the single current question -- the founder's
        already-answered turns are safely in `answers`, they were just never sent
        back to render. This backs GET /diagnosis/current's `history` field so a
        resumed session can rebuild its own transcript instead of looking like
        the prior answers vanished.
        """
        stmt = (
            select(Question.question_text, Question.category, Answer.answer_text, Answer.answered_at)
            .join(Answer, Answer.question_id == Question.question_id)
            .where(Answer.session_id == session_id)
            .order_by(Answer.answered_at.asc())
        )
        return list(self.db.execute(stmt).all())
