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
