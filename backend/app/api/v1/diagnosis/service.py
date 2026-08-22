"""Business logic for the diagnosis assessment flow.

Owns the transaction boundary. `submit_answer` commits in two short steps
rather than one long one -- see its docstring for why: holding a single
transaction open across the LLM calls in between let a pooled/proxied
Postgres connection (Supabase's pooler, live-confirmed) get killed mid-query
while idle-in-transaction, failing the whole request after the answer had
already been written. Every other public method still commits once.
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.advisor import AnswerInsight, NextQuestionAdvisor, resolve_next
from app.api.v1.diagnosis import incremental_confidence
from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.core.config import settings
from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.plans.catalog import get_plan
from app.plans.errors import DiagnosisAlreadyCompletedError
from app.models import (
    Answer,
    DiagnosisSession,
    Founder,
    Question,
    RoutingState,
    ScoreLabel,
    SessionState,
    SessionStatus,
)

#: Score paired with ScoreLabel.AMBER for an answer the advisor could not assess.
#: Matches the Amber band in the question-score config (green 0 / amber 1 / red 2).
_FALLBACK_SCORE = Decimal("1")


class FounderDnaNotCompleteError(AppError):
    def __init__(
        self,
        message: str = (
            "Complete the Founder DNA phase (POST /founder-dna/start) before "
            "starting a diagnosis."
        ),
    ):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class CurrentProblemNotCompleteError(AppError):
    def __init__(
        self,
        message: str = (
            "Describe the current problem (POST /current-problem/start) before "
            "starting a diagnosis."
        ),
    ):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class SessionNotFoundError(AppError):
    def __init__(self, message: str = "No active diagnosis session was found."):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class SessionNotActiveError(AppError):
    def __init__(self, message: str = "This diagnosis session is no longer active."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class QuestionMismatchError(AppError):
    def __init__(self, message: str = "That question is not the current question."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class DuplicateAnswerError(AppError):
    def __init__(self, message: str = "This question has already been answered."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class DiagnosisPersistenceError(AppError):
    def __init__(self, message: str = "Could not save the diagnosis session."):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


#: What Ally says when an answer did not address the question that was asked.
#:
#: Deliberately blames the miss, not the founder, and does not quote the answer
#: back at them. One fixed line rather than a generated one: this fires on the
#: same request that already spent an LLM call, and a second call to phrase an
#: apology is not worth the wait.
_REPROMPT = (
    "That one got away from the question I asked — I think you answered a "
    "different one. Take another run at this one; a specific example is worth "
    "more than a tidy answer."
)


def should_discard_as_unresponsive(
    insight, *, created_here: bool, already_reprompted: bool
) -> bool:
    """Whether to discard this answer and re-ask the question.

    A pure predicate rather than an inline condition because it encodes a safety
    property, and safety properties deserve a test that does not need a database:

      * fails OPEN -- no insight (no advisor, failed call, unparseable reply) or
        `responsive` True leaves the answer standing;
      * only ever discards an answer THIS request inserted, never one recovered
        by the resume/race paths, which belongs to a call that already completed;
      * discards at most ONCE per question. The verdict is a model's and can be
        wrong, and a wrong one must never leave a founder unable to continue.
    """
    if insight is None or insight.responsive:
        return False
    return created_here and not already_reprompted


def needs_fallback_score(insight) -> bool:
    """Whether a KEPT answer must be given the neutral fallback band.

    A pure predicate for the same reason as the one above: it encodes the "an
    answer is never left unscored" property, and that property was quietly
    broken by a condition that looked right.

    The broken version asked `insight is None`, on the assumption that an
    insight always carries a usable band. It does not: advisor._parse
    deliberately nulls score_label for any label outside {green, amber, red}
    while still returning an insight (so the responsiveness verdict and the
    next-question pick in the same reply are not thrown away). That left a
    third state -- an insight with no band -- in which _apply_insight no-ops
    and the fallback never runs. The answer is kept, shown back to the founder
    as answered, and then dropped at classification time by
    StoredScoreAnswerClassifier, which refuses to guess a band. Enough of them
    in one session and NoClassifiableAnswersError kills the whole report.

    So the question is about the SCORE, not about the object carrying it.
    """
    return insight is None or insight.score_label is None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosisService:
    def __init__(self, db: Session, *, advisor: NextQuestionAdvisor | None = None):
        self.db = db
        self.repository = DiagnosisRepository(db)
        self.engine = QuestionSelectionEngine(self.repository)
        # Optional adaptive next-question advisor (Hybrid). None => deterministic.
        self.advisor = advisor

    # --- Public API ---

    def _check_diagnosis_allowance(self, founder: Founder) -> None:
        """Bound how many diagnoses a founder may ever COMPLETE -- a lifetime
        cap, not a monthly one.

        Diagnosis is unmetered by tokens on purpose, so a count is the only thing
        limiting what it costs -- roughly 24,400 tokens a run. Only completed
        sessions count: a founder who abandoned one mid-way and starts fresh has
        not "used" their diagnosis, since they never reached a report. (The
        resume path in start_session already handles the in-progress case and
        never reaches this check at all -- see there.)

        Fails OPEN on an unreadable plan or count: refusing a founder their
        diagnosis because a lookup failed is a worse outcome than serving one
        extra, and this is a cost control, not a security boundary.
        """
        try:
            plan = get_plan(founder.plan_type)
            limit = plan.diagnosis_lifetime_limit
            if limit <= 0:                      # 0 = unlimited
                return
            used = self.repository.count_completed_sessions(founder.founder_id)
        except Exception:                       # noqa: BLE001
            logger.warning(
                "Diagnosis limit check failed; allowing the diagnosis",
                extra={"founder_id": founder.founder_id},
            )
            return

        if used >= limit:
            raise DiagnosisAlreadyCompletedError(used, limit)

    def start_session(self, founder: Founder) -> tuple[DiagnosisSession, Question | None, bool]:
        """Start a diagnosis session, or resume the founder's active one.

        Resuming rather than creating a second session is deliberate: the
        schema permits multiple in-progress rows per founder, and a double-
        submitted "Start" would otherwise silently fork the assessment and
        strand the answers already given.

        Returns (session, first_question, resumed).
        """
        # Live-reproduced: without this lock, two near-simultaneous calls both
        # read "no active session, 0 used this month" before either had
        # committed -- both passed the check below and both created a
        # session, turning a limit of 1 into 2. Held for the rest of this
        # transaction; a concurrent second call blocks here until the first
        # commits, then correctly sees the session it just created.
        self.repository.lock_founder_for_diagnosis_start(founder.founder_id)

        existing = self.repository.get_active_session_for_founder(founder.founder_id)
        if existing is not None:
            logger.info(
                "Resuming existing diagnosis session",
                extra={"founder_id": founder.founder_id},
            )
            question = self._current_question_for(existing, founder)
            # Release the founder-row lock taken above. Returning straight out of
            # here held it for the rest of the request -- through question lookup
            # and response serialisation -- for a path that writes nothing.
            # Nothing uncommitted is lost: the pointer repair inside
            # _current_question_for commits its own work.
            self.db.rollback()
            return existing, question, True

        # The doc's three sections in order: Founder DNA, then the Current
        # Problem symptom capture, then this -- the Business DNA interrogation.
        # The symptom gate matters diagnostically, not just for tidiness: the
        # report's whole Page 3 move is quoting what the founder SAID the
        # problem was and contradicting it with what the interrogation found.
        # Interrogate first and there is nothing to contradict.
        #
        # Only gates a NEW diagnosis -- same reasoning as the allowance check
        # right below: an in-progress assessment (the resume path above) must
        # always be continuable even if this were somehow unset later.
        if founder.founder_dna_completed_at is None:
            raise FounderDnaNotCompleteError()
        if founder.current_problem_completed_at is None:
            raise CurrentProblemNotCompleteError()

        # Only a NEW diagnosis is bounded. The resume path above has already
        # returned, so an in-progress assessment can always be continued -- the
        # limit can never strand someone partway through.
        self._check_diagnosis_allowance(founder)

        session = DiagnosisSession(
            founder_id=founder.founder_id,
            status=SessionStatus.IN_PROGRESS.value,
            questions_answered_count=0,
            session_state=SessionState.STABLE.value,
            routing_state=RoutingState.CONTINUE.value,
            founder_stage_id=founder.stage_id,
            founder_industry_id=founder.industry_mapped_id,
            started_at=_utcnow(),
            last_activity_at=_utcnow(),
        )

        try:
            self.repository.add_session(session)

            first_question = self.engine.select_next_question(session, founder)
            self._attach_question(session, first_question)

            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # Most likely a CHECK/FK violation -- surfaced explicitly because
            # the generic 500 handler would hide which constraint failed.
            logger.error(
                "Integrity error creating diagnosis session",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error creating diagnosis session",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError()

        self.db.refresh(session)
        logger.info(
            "Started diagnosis session",
            extra={"founder_id": founder.founder_id},
        )
        return session, first_question, False

    def get_current_question(
        self, founder: Founder
    ) -> tuple[DiagnosisSession, Question | None, list[tuple[str, str, str, datetime]], bool]:
        """Current question for the founder's active session, plus everything
        already answered so far.

        404s when there is no active session -- the caller must POST /start
        first. This is a read; it does not create one implicitly.

        Returns (session, question, history, completed_now). That last flag is
        not incidental: _current_question_for repairs a null pointer by
        re-selecting, and _attach_question -- the single authority on "no
        question left" -- COMPLETES the session when the bank is exhausted, the
        budget is spent, or the incremental scorer already flipped
        routing_state to generate_report. So a plain page reload really can end
        a diagnosis. Only POST /answer used to schedule the completion
        notifier, which meant a session completed on this path had no reasoning
        run dispatched at all: the founder sat on the Thinking screen polling
        for a report nothing was building, while their one free diagnosis was
        already counted as spent. The router schedules the notifier when this
        is True, so completion means the same thing on both paths.
        """
        session = self.repository.get_active_session_for_founder(founder.founder_id)
        if session is None:
            raise SessionNotFoundError()

        was_in_progress = session.status == SessionStatus.IN_PROGRESS
        history = self.repository.full_qa_history(session.session_id)
        question = self._current_question_for(session, founder)
        completed_now = was_in_progress and session.status == SessionStatus.COMPLETED

        return session, question, history, completed_now

    def abandon_session(self, founder: Founder) -> DiagnosisSession:
        """Abandon the founder's active session so they can start a new one.

        SessionStatus.ABANDONED existed with no writer anywhere in the app,
        which made it a state the system could describe but never reach -- and
        start_session resumes an in-progress session unconditionally. A session
        that had wedged (a pointer at a retired question, a stage group that
        yields no candidates) therefore trapped the founder permanently: every
        POST /start handed back the same broken session and there was no way
        out without an operator editing the row.

        Deliberately does NOT consume the lifetime allowance -- that cap counts
        completed sessions only, precisely because someone who never reached a
        report has not had their diagnosis (see _check_diagnosis_allowance).
        """
        session = self.repository.get_active_session_for_founder(founder.founder_id)
        if session is None:
            raise SessionNotFoundError()

        session.status = SessionStatus.ABANDONED.value
        session.current_question_id = None
        session.current_category = None
        session.last_activity_at = _utcnow()
        session.updated_at = _utcnow()

        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error abandoning diagnosis session",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError("Could not abandon the session.")

        logger.info(
            "Abandoned diagnosis session",
            extra={"founder_id": founder.founder_id, "session_id": session.session_id},
        )
        self.db.refresh(session)
        return session

    async def submit_answer(
        self,
        founder: Founder,
        question_id: int,
        answer_text: str,
    ) -> tuple[DiagnosisSession, Question | None, str | None]:
        """Store an answer, advance progress, and select the next question.

        Returns (session, next_question, reprompt). `next_question` is None once
        the bank is exhausted, at which point the session is marked completed.

        `reprompt` is non-None when the answer did not answer the question that
        was asked: nothing was kept, progress did not move, `next_question` is
        the SAME question, and the string is what Ally says back. See the
        responsiveness block below for why that has to undo a commit.

        Adaptive (Hybrid): when an advisor is wired, the LLM reads the answer,
        scores it (persisted on the answer), and re-ranks the deterministic
        shortlist to pick the next question. It fails open to the deterministic
        pick on any error, so the flow always progresses.

        Two commits, not one: the answer itself is written and committed
        FIRST, before the two LLM calls below (the advisor pick, then
        incremental confidence). Live-confirmed the old single-transaction
        version could sit idle-in-transaction across both of those for tens of
        seconds, long enough for Supabase's pooled connection to be closed out
        from under it -- the request then died with a raw SSL/connection error
        on whatever query ran next, even though the answer itself was fine.
        Committing the answer first means that failure mode now costs a
        recoverable progress-update retry instead of a lost answer or a 500 to
        the founder. The recovery path just below (an existing answer for the
        current question is a retry of THIS call, not a duplicate submission)
        is what makes that retry safe.
        """
        session = self.repository.get_active_session_for_founder(founder.founder_id)
        if session is None:
            raise SessionNotFoundError()

        self._assert_active(session)

        # Guard against a stale client replaying an old question. Without this,
        # a retried request could attach an answer to the wrong question.
        #
        # The pointer is REPAIRED before the comparison rather than the
        # comparison being skipped when it is null. Gating the guard on
        # "current_question_id is not None" made a null pointer accept ANY
        # question_id the client sent -- and a null pointer on an active session
        # is a state that genuinely occurs (a request that died between session
        # creation and question selection, which is exactly why
        # _current_question_for exists to self-heal it). The result was an
        # answers row, scored and counted, for a question the founder was never
        # shown. Repair first, then compare unconditionally: after this call the
        # session is sitting on a real question, so a mismatch is a mismatch.
        if session.current_question_id is None:
            self._current_question_for(session, founder)
            # Repair can legitimately land on "there is nothing left to ask",
            # which completes the session. Say that rather than reporting the
            # now-null pointer as a question mismatch.
            self._assert_active(session)

        if question_id != session.current_question_id:
            raise QuestionMismatchError(
                f"Expected question {session.current_question_id}, received {question_id}."
            )

        question = self.repository.get_question_by_id(question_id)
        if question is None:
            raise QuestionMismatchError(f"Question {question_id} does not exist.")

        created_here = False
        answer = self.repository.get_answer(session.session_id, question_id)
        if answer is not None:
            # Not a duplicate submission -- a genuine one would target a
            # question_id that is no longer session.current_question_id, and
            # that is already rejected above by the mismatch check. Reaching
            # here means: same session, same still-current question, an
            # answer already on file for it. The only way that happens is a
            # previous call to this method got as far as committing the
            # answer and then failed before its second commit (the pooler
            # drop this docstring describes). Resume from here instead of
            # raising DuplicateAnswerError at a founder who only answered once.
            logger.info(
                "Answer already saved; resuming the progress-update step "
                "that did not complete last time",
                extra={
                    "founder_id": founder.founder_id,
                    "session_id": session.session_id,
                    "question_id": question_id,
                },
            )
        else:
            # Tracked because the responsiveness check below may need to undo this
            # insert, and it must only ever undo an answer IT created -- never one
            # recovered by the resume/race paths above, which belongs to a call
            # that already completed.
            created_here = True
            answer = Answer(
                session_id=session.session_id,
                founder_id=founder.founder_id,
                question_id=question_id,
                answer_text=answer_text,
                is_follow_up=False,
                is_distress_flagged=False,
                answered_at=_utcnow(),
            )
            self.repository.add_answer(answer)
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                # Could be a genuine integrity problem, or two near-simultaneous
                # requests for the same (session_id, question_id) racing each
                # other -- a double-click, or a client retry that overlapped
                # the original request instead of following it. The unique
                # constraint on answers(session_id, question_id) (see
                # uq_answers_session_question) is what makes the loser's
                # insert fail here rather than silently creating a duplicate
                # row + re-billing the LLM advisor call. Re-fetch to tell the
                # two cases apart: if the row exists now, this WAS the race,
                # not a failure -- resume from the winner's row exactly like
                # the pooler-drop recovery path above, instead of surfacing an
                # error to a founder who only submitted once.
                existing = self.repository.get_answer(session.session_id, question_id)
                if existing is not None:
                    logger.info(
                        "Concurrent duplicate answer submission detected; "
                        "resuming from the row the other request already "
                        "committed instead of failing this one.",
                        extra={
                            "founder_id": founder.founder_id,
                            "session_id": session.session_id,
                            "question_id": question_id,
                        },
                    )
                    answer = existing
                else:
                    logger.error(
                        "Integrity error saving answer",
                        extra={"founder_id": founder.founder_id},
                        exc_info=exc,
                    )
                    raise DiagnosisPersistenceError("Could not save the answer.")
            except SQLAlchemyError as exc:
                self.db.rollback()
                logger.error(
                    "Database error saving answer",
                    extra={"founder_id": founder.founder_id},
                    exc_info=exc,
                )
                raise DiagnosisPersistenceError("Could not save the answer.")

        # The answer is safely committed from here on. Everything below is the
        # slow part (two LLM calls) and touches only session-progress fields,
        # which the recovery path above can always redo from scratch.
        next_question, insight = await self._choose_next_question(
            session, founder, question, answer
        )

        # --- responsiveness -------------------------------------------------
        # The answer is already committed by this point, and deliberately so
        # (see the docstring: the two LLM calls below used to hold a transaction
        # open long enough for Supabase's pooler to drop the connection). So a
        # "this did not answer the question" verdict cannot simply decline to
        # save -- it has to delete the row it just wrote. That is safe precisely
        # because `created_here` narrows it to this call's own insert.
        #
        # Why gate at all, when the founder can write whatever they like: a
        # non-answer is scored like an answer, and that score is load-bearing.
        # Live-observed on 2026-08-19 -- a scripted answer about time allocation
        # landed on "Think of the last time you faced real uncertainty outside of
        # work", correctly scored Red for having no evidence in it, and two such
        # Reds on distress-tagged questions flipped the whole report into the
        # distress variant, opening it with "what you are carrying right now
        # matters more than any diagnosis". The measurement was of nothing.
        #
        # Fails open in every direction: no advisor, a failed call, an
        # unparseable response or a model that does not know the field all leave
        # `responsive` True and the answer stands.
        # ...but only ONCE per question. The verdict is a model's and can be
        # wrong, and a wrong one must never leave a founder unable to continue:
        # without this, the same question is discarded and re-asked indefinitely
        # and the diagnosis dead-ends. Live-reproduced before this existed -- one
        # question rejected three times running, the run stalled at 15 of 30 with
        # no report. Second attempt is accepted and scored like any other answer.
        if should_discard_as_unresponsive(
            insight,
            created_here=created_here,
            already_reprompted=session.reprompted_question_id == question_id,
        ):
            logger.info(
                "Answer did not address the question; discarding and re-asking",
                extra={
                    "founder_id": founder.founder_id,
                    "session_id": session.session_id,
                    "question_id": question_id,
                },
            )
            try:
                session.reprompted_question_id = question_id
                self.db.delete(answer)
                # The founder is mid-conversation, not idle: a run of reprompts
                # left last_activity_at frozen at the last ACCEPTED answer, so a
                # session actively being worked on looked stale to anything that
                # reads activity.
                session.last_activity_at = _utcnow()
                session.updated_at = _utcnow()
                self.db.commit()
                return session, question, _REPROMPT
            except SQLAlchemyError as exc:
                # Keeping a non-answer is worse than failing the request, but not
                # much. Let it stand rather than 500 at a founder who did nothing
                # wrong -- and then fall THROUGH to the accept path below rather
                # than returning here. Returning early reported accepted=true for
                # an answer that was never scored, whose progress counters were
                # never recomputed and whose session was never advanced: the
                # founder saw the same question re-asked as though it were the
                # next one, and an unscored row was left behind to be dropped at
                # classification time. If the row is staying, it is treated
                # exactly like any other kept answer.
                self.db.rollback()
                logger.warning(
                    "Could not discard the unresponsive answer; keeping and "
                    "scoring it like an accepted one",
                    extra={"founder_id": founder.founder_id},
                    exc_info=exc,
                )

        # The answer is being kept, so it gets the score the advisor produced --
        # including when the one-reprompt bound accepted it over a second
        # unresponsive verdict. Responsiveness and quality are separate axes and
        # the model reported both; dropping the score because of the other field
        # leaves the row unscored, and an unscored answer is not neutral. With
        # ANSWER_CLASSIFIER=llm it is re-scored from scratch at reasoning time,
        # which is how seven answers in one live session came back Red, two of
        # them on distress-tagged questions, and tripped
        # DISTRESS_QUESTIONS_TRIGGER -- so a founder whose language detector
        # reported "Open and Engaged" was handed a distress report telling him
        # burnout and isolation appeared to be active blockers.
        if not needs_fallback_score(insight):
            self._apply_insight(answer, insight)
        else:
            # No USABLE score means the advisor was absent, FAILED (timeout, bad
            # reply), or returned a label outside {green, amber, red} -- advisor
            # _parse deliberately nulls score_label in that last case while still
            # returning an insight, so gating this branch on `insight is None`
            # alone let an unparseable label fall between the two: _apply_insight
            # no-ops on a null score_label, and the fallback never ran.
            # Leaving the row unscored is not neutral -- it is silent
            # data loss: StoredScoreAnswerClassifier refuses to guess a band and
            # the reasoning pipeline drops the answer entirely
            # ("Skipping unscored answer during classification"). Measured on one
            # live session, six of the founder's answers were kept, shown back to
            # them as answered, and then contributed nothing to their diagnosis.
            #
            # An advisor outage must cost adaptivity, never the founder's answer.
            # AMBER is the deliberate choice: it is the middle band, so an
            # unassessable answer neither manufactures a clean signal (green) nor
            # invents a problem the founder may not have (red).
            self._apply_fallback_score(answer)

        # Serialize the progress update against a concurrent answer to the SAME
        # question. Taken here rather than at the top of the request on purpose:
        # the two LLM calls above must not run inside a held transaction (see
        # this method's docstring). The lock therefore covers only the short
        # write below, and a request that lost the race finds the pointer has
        # already moved and returns the winner's question instead of overwriting
        # it with a second, independently chosen one.
        try:
            self.repository.lock_session_for_update(session.session_id)
            self.db.refresh(session)
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error locking session for the progress update",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError("Could not save your progress. Please try again.")

        if session.current_question_id is not None and session.current_question_id != question_id:
            logger.info(
                "Concurrent answer already advanced this session; returning the "
                "question it moved to instead of overwriting it",
                extra={
                    "founder_id": founder.founder_id,
                    "session_id": session.session_id,
                    "question_id": question_id,
                },
            )
            self.db.rollback()  # release the lock; the winner already committed
            return session, self._current_question_for(session, founder), None

        try:
            # Derived from the actual row count, not incremented -- a retry
            # through the recovery path above must not double-count an answer
            # it did not just add.
            session.questions_answered_count = len(
                self.repository.get_answered_question_ids(session.session_id)
            )
            session.last_activity_at = _utcnow()
            session.updated_at = _utcnow()

            # Score the session as it now stands, BEFORE deciding whether to ask
            # another question. This is what turns the 60/80 thresholds from
            # stored values into a decision: recompute sets routing_state, and
            # _attach_question reads it to decide whether the diagnosis is done.
            # Ordering matters -- scoring after attaching would decide on the
            # previous answer's evidence and always be one question late.
            await incremental_confidence.recompute(self.db, session, founder)

            # Cleared on every accepted answer: the marker means "this exact
            # question is on its second attempt" and must not survive the move to
            # the next one.
            session.reprompted_question_id = None
            self._attach_question(session, next_question)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            logger.error(
                "Integrity error saving diagnosis progress",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError("Could not save your progress. Please try again.")
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error saving diagnosis progress",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError("Could not save your progress. Please try again.")

        self.db.refresh(session)

        # _attach_question is the single authority on whether a next question
        # exists -- it nulls current_question_id when it decides the session is
        # done. `next_question` here is the candidate picked BEFORE that
        # decision, so on the completing answer it holds a real question the
        # session was never actually moved to. Returning it advertised
        # `status: "completed"` and a populated `next_question` in the same
        # response, and a client trusting the question over the status would
        # ask it and get a 409.
        if session.status != SessionStatus.IN_PROGRESS.value:
            return session, None, None
        return session, next_question, None

    async def _choose_next_question(
        self, session: DiagnosisSession, founder: Founder, answered: Question, answer: Answer
    ) -> tuple[Question | None, AnswerInsight | None]:
        """Deterministic pick, optionally overridden by the LLM advisor.

        Never raises: an advisor failure or an out-of-shortlist recommendation
        falls back to the deterministic head, so the assessment always advances.

        Returns the insight alongside the pick so the caller can act on its
        responsiveness verdict; None when no advisor ran or it failed.
        """
        candidates = self.engine.candidate_questions(session, founder)
        if not candidates:
            return None, None  # bank exhausted -> completion

        ordered = self.engine.order_candidates(candidates, session)
        if self.advisor is None:
            return ordered[0], None

        shortlist = ordered[: settings.ADAPTIVE_SHORTLIST_SIZE]
        history = self.repository.recent_qa(session.session_id, limit=5)
        insight: AnswerInsight | None = None
        try:
            insight = await self.advisor.analyze(
                answered_question=answered,
                answer_text=answer.answer_text,
                shortlist=shortlist,
                history=history,
            )
        except Exception as exc:  # advisor must never break the flow
            logger.warning(
                "adaptive advisor raised; using deterministic pick",
                extra={"founder_id": founder.founder_id, "stage": "adaptive_questions"},
                exc_info=exc,
            )

        # Scoring is the CALLER's decision, not this method's: an answer is
        # scored if and only if it is kept, and only submit_answer knows that.
        # This used to score only `responsive` answers, which silently created a
        # third state -- kept but unscored -- for every answer accepted by the
        # one-reprompt bound. See submit_answer for what that cost.
        return resolve_next(ordered, shortlist, insight), insight

    def _apply_fallback_score(self, answer: Answer) -> None:
        """Score a kept answer the advisor could not assess.

        Logged at WARNING, not INFO: a fallback score means this answer carries
        no real assessment, and a run full of them is a degraded diagnosis that
        would otherwise look identical to a healthy one.
        """
        answer.score_label = ScoreLabel.AMBER.value
        answer.score = _FALLBACK_SCORE
        logger.warning(
            "Answer kept without an advisor score; applying neutral fallback",
            extra={
                "stage": "answer_scoring_fallback",
                "answer_id": answer.answer_id,
                "question_id": answer.question_id,
                "score_label": ScoreLabel.AMBER.value,
            },
        )

    def _apply_insight(self, answer: Answer, insight: AnswerInsight) -> None:
        """Persist the LLM's Green/Amber/Red read on the answer, so the reasoning
        pipeline reuses it (via the stored-score classifier) instead of re-scoring."""
        if insight.score_label is not None:
            answer.score_label = insight.score_label
            answer.score = insight.score

    # --- Internals ---

    def _assert_active(self, session: DiagnosisSession) -> None:
        if session.status != SessionStatus.IN_PROGRESS:
            raise SessionNotActiveError(
                f"Session {session.session_id} has status '{session.status}'."
            )

    def _attach_question(
        self,
        session: DiagnosisSession,
        question: Question | None,
    ) -> None:
        """Point the session at `question`, or complete it when None.

        Completion lives here rather than in the engine so that "no questions
        left" has exactly one meaning across every entry point.
        """
        # Completion has three triggers, and only the first is a success:
        #
        #   1. confidence >= CONFIDENCE_GENERATE_REPORT_MIN -- enough is known
        #   2. the question budget is spent (MAX_DIAGNOSIS_QUESTIONS)
        #   3. no eligible question is left in the bank
        #
        # (1) is set by the incremental scorer, which flips routing_state to
        # generate_report; this reads that decision rather than re-deriving it.
        # (2) is why the budget exists at all: the Stage 0->1 bank holds 569
        # questions and exhaustion (3) is not a stopping point any real founder
        # reaches -- before the cap, every session simply ran until abandoned,
        # which is why no diagnosis had ever completed.
        budget_spent = (session.questions_answered_count or 0) >= settings.MAX_DIAGNOSIS_QUESTIONS
        confident = session.routing_state == RoutingState.GENERATE_REPORT.value

        if question is None or budget_spent or confident:
            session.current_question_id = None
            session.current_category = None
            session.status = SessionStatus.COMPLETED.value
            session.completed_at = _utcnow()
            # Only claim report-readiness when the score actually earned it. A
            # session that ran out of budget or questions below the threshold is
            # completed but NOT confident, and stamping generate_report on it --
            # as this did unconditionally -- told the report layer the diagnosis
            # was conclusive when it was merely over. Leaving routing_state
            # alone is the whole of that rule; the `if not confident` branch
            # that used to sit here assigned the attribute to itself and read
            # as an active guard doing something it was not.
            session.routing_state = session.routing_state or RoutingState.CONTINUE.value
            return

        session.current_question_id = question.question_id
        session.current_category = question.category

    def _current_question_for(
        self,
        session: DiagnosisSession,
        founder: Founder,
    ) -> Question | None:
        """Question the session is currently sitting on.

        Self-heals a session whose pointer is null while it is still active --
        that can happen if a previous request died between creating the session
        and selecting a question. Re-selecting is safe because selection is
        deterministic and derived from what has been answered.
        """
        if session.current_question_id is not None:
            return self.repository.get_question_by_id(session.current_question_id)

        if session.status != SessionStatus.IN_PROGRESS:
            return None

        question = self.engine.select_next_question(session, founder)
        self._attach_question(session, question)

        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error repairing session question pointer",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError()

        return question
