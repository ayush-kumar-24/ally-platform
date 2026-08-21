"""Database access for the diagnosis module.

This layer only builds and runs queries. It holds no business rules, raises no
domain errors, and never commits -- transaction boundaries belong to the
service so that a single request stays atomic.
"""

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy import text as _text
from sqlalchemy.orm import Session

from app.models import Answer, DiagnosisSession, Question, SessionStatus
from app.models.schema import FounderDnaAnswers, FounderDnaQuestions


class DiagnosisRepository:
    def __init__(self, db: Session):
        self.db = db
        #: Request-lifetime cache for problem_to_pillar() -- see its docstring.
        self._problem_to_pillar: dict[int, int] | None = None

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

    def list_candidate_questions(
        self,
        session_id: int,
        stage_groups: list[str],
        founder_id: int | None = None,
    ) -> list[Question]:
        """Every question still unanswered in this session and valid for the
        founder's stage.

        Questions with a NULL `primary_stage_group` are stage-agnostic and
        always eligible, which is why the predicate ORs rather than filters.

        Note the bank currently contains NO such rows -- every one of the 2127
        questions is pinned to exactly one group. An earlier version of this
        docstring claimed stage-agnostic questions were "the majority of the
        bank"; that has not been true for some time, and believing it hides
        how narrow a single stage group can be. Market Clarity had just four
        questions reachable by a scaling founder until
        `f6d2a81c53e7_retag_market_clarity_scaling_questions` moved 134
        mis-tagged ones. Check the real distribution before assuming breadth.

        Ordering is left to the engine -- this returns an unordered candidate
        set on purpose.
        """
        answered = select(Answer.question_id).where(Answer.session_id == session_id)

        stmt: Select = select(Question).where(
            Question.question_id.not_in(answered),
            (Question.primary_stage_group.is_(None))
            | (Question.primary_stage_group.in_(stage_groups)),
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
