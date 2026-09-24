"""Question Selection Engine.

Decides which question comes next. It owns the ordering policy only -- it never
touches the database directly, it asks the repository for a candidate set and
ranks it. That keeps the policy unit-testable without a live Postgres.

Selection is fully deterministic. Given the same session and the same question
bank, the same question comes out every time, which matters because a founder
who reloads mid-assessment must not see the question change under them.

SCORING IS OUT OF SCOPE. Two hooks are stubbed but intentionally inert:
follow-up triggering and adaptive re-ordering both depend on a scored answer,
and inventing a trigger rule now would bake in behaviour the scoring engine
would have to unpick later.
"""

from app.api.v1.diagnosis.context_scope import (
    context_tokens,
    gated_problem_codes,
    gated_root_cause_codes,
)
from app.api.v1.diagnosis.industry_scope import (
    excluded_question_ids,
    industry_id_for,
    normalise_weights,
    relevance_ranker,
)
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.stage_scope import resolve_scope
from app.core.logger import logger
from app.models import (
    DiagnosisSession,
    Founder,
    Question,
    QuestionPriority,
    RoutingState,
    StageGroup,
)

# Order in which categories are worked through. Founder Psychology leads
# because the psychological questions calibrate how the operational answers
# should be read; Fundraising trails because it is the most situational.
CATEGORY_SEQUENCE: tuple[str, ...] = (
    "Founder Psychology",
    "Idea & Validation",
    "Product",
    "Go-To-Market",
    "Sales & Revenue",
    "Team & Leadership",
    "Operations & Systems",
    "Fundraising",
)

# Rank CORE ahead of SUPPLEMENTARY within a category.
_PRIORITY_RANK: dict[str, int] = {
    QuestionPriority.CORE.value: 0,
    QuestionPriority.SUPPLEMENTARY.value: 1,
}

# ---------------------------------------------------------------------------
# `questions.primary_stage_group` buckets questions into three groups, but no
# column links a founder's stage (founder_stages.stage_id, 1..8) to those
# buckets. This mapping is that link -- a business rule with no database
# backing, derived from stage_order:
#
#     Ideation(1)                                     -> Stage 0
#     Validation(2), Prototype/MVP(3), Early Trac.(4) -> Stage 0->1
#     Growth(5) .. Exit(8)                            -> Stage 1->10+
#
# These boundaries are the ones onboarding asks against: the founder picks the
# group first and the exact stage second, so the two must agree or a founder
# would be shown questions for a group they did not choose. The picker is
# defined in frontend/src/data/onboardingQuestions.js (STAGE_GROUPS) -- change
# both together.
#
# Note Validation sits in Stage 0->1, not Stage 0: a founder testing demand
# already has something to test, which is past pure ideation.
# ---------------------------------------------------------------------------
_STAGE_ORDER_TO_GROUP: tuple[tuple[int, StageGroup], ...] = (
    (1, StageGroup.STAGE_0),
    (4, StageGroup.STAGE_0_TO_1),
    (8, StageGroup.STAGE_1_TO_10_PLUS),
)


def resolve_stage_groups(founder: Founder) -> list[str]:
    """Question stage-groups eligible for this founder.

    A founder with no stage recorded is eligible for all three groups rather
    than none: onboarding may be incomplete, and returning zero questions would
    dead-end the assessment on the first request.
    """
    return stage_groups_for(founder.stage)


def stage_groups_for(stage) -> list[str]:
    """Same mapping as `resolve_stage_groups`, but over a `FounderStage` row
    (or None) directly rather than a full `Founder` ORM object with a loaded
    `.stage` relationship. Callers that already fetched the stage separately
    (e.g. AllyContextBuilder, which looks it up by id rather than relying on
    relationship loading) use this instead of needing a founder object shaped
    exactly like the diagnosis module's own -- one mapping, two entry points.
    """
    # getattr, not stage.stage_order: a real FounderStage row always has this
    # (NOT NULL column), but a stage that exists without a readable order is
    # the same "we don't actually know" situation as no stage at all -- fail
    # open to every group rather than raise, same convention as stage is None.
    order = getattr(stage, "stage_order", None)
    if stage is None or order is None:
        return [group.value for group in StageGroup]

    for max_order, group in _STAGE_ORDER_TO_GROUP:
        if order <= max_order:
            return [group.value]

    return [StageGroup.STAGE_1_TO_10_PLUS.value]


def _sort_key(question: Question) -> tuple[int, int, int, int]:
    """Deterministic ranking key WITHIN one round-robin round.

    Category sequence, then CORE before SUPPLEMENTARY, then easiest first so
    the founder warms up before the harder probes, then question_id purely as a
    tie-breaker so the order can never wobble between requests.

    A category outside CATEGORY_SEQUENCE sorts last rather than raising -- a
    newly seeded category should degrade to "asked late", not break the
    assessment.

    NOTE: this key alone is not the ask-order any more. On its own it sorts
    strictly by category, which meant the first category was drained before
    the second was ever reached -- see `_round_robin_key_for`.
    """
    try:
        category_rank = CATEGORY_SEQUENCE.index(question.category)
    except ValueError:
        category_rank = len(CATEGORY_SEQUENCE)

    priority_rank = _PRIORITY_RANK.get(question.priority, len(_PRIORITY_RANK))

    return (category_rank, priority_rank, question.difficulty_level, question.question_id)


class QuestionSelectionEngine:
    def __init__(self, repository: DiagnosisRepository):
        self.repository = repository

    def select_next_question(
        self,
        session: DiagnosisSession,
        founder: Founder,
    ) -> Question | None:
        """Next question for this session, or None when the bank is exhausted.

        None is the completion signal: the service turns it into a completed
        session. It is a legitimate outcome, not an error.
        """
        candidates = self.candidate_questions(session, founder)
        if not candidates:
            return None
        return min(candidates, key=self._sort_key_for(session, founder))

    def _round_robin_key_for(
        self, session: DiagnosisSession, founder: Founder | None = None
    ):
        """The GATHER-phase key: one question per pillar before any pillar
        gets a second.

        Why this exists. The six readiness pillars are what the report and the
        dashboard are built on, and a pillar with no answers scores None --
        it renders blank, not low. Selection used to order by CATEGORY_SEQUENCE
        alone, which is a strict sort, so the first category was exhausted
        before the second was reached. "Founder Psychology" leads that sequence
        and carries 287 questions, all of them pillar 1 (Founder Readiness),
        against a MAX_DIAGNOSIS_QUESTIONS budget of 30 -- so every session
        spent its entire budget inside pillar 1 and the other five pillars were
        never asked about at all. Same failure that put the Founder DNA phase
        on a mandatory arc rather than a per-dimension sweep.

        The fix is to make the pillar's turn the PRIMARY sort term:
        `answered_in_that_pillar` is the round number, so every pillar sits at
        round 0 until it has been asked once, then drops behind the pillars
        still at 0.

        The SECOND term round-robins categories within the pillar, and it
        matters as much as the first. Pillar-only round-robin covered all six
        but read each one off a single category -- Revenue Maturity was scored
        from five Go-To-Market questions in a row while Financial Management,
        Sales Execution and Business Model Design (its other 336 questions)
        went unasked. A pillar score built from one narrow slice is not much
        more honest than no score at all, and "pillar under most strain" is a
        headline claim in the report.

        `_sort_key` still decides WHICH question represents a pillar-category
        within a round, so the category sequence, CORE-first and easiest-first
        intents all survive -- they just no longer starve anything.

        Counting ANSWERED (not asked) questions is deliberate: a question shown
        and abandoned must not consume its pillar's turn.

        Pillars OUT OF SCOPE for the founder's stage never reach this key --
        `candidate_questions` has already removed them -- so "every pillar" here
        means every pillar the stage is diagnosed on. At ideation that is four
        (Business DNA Part 3), and the round-robin spreads the budget across
        those four rather than manufacturing turns for Revenue Maturity and
        Team & Leadership, which have nothing to say yet. See `stage_scope.py`.

        Degrades to `_sort_key` if the pillar map is unavailable for any
        reason -- a coverage optimisation must never be able to stop the
        assessment from finding a next question.
        """
        try:
            with self.repository.db.begin_nested():
                problem_to_pillar = self.repository.problem_to_pillar()
                per_cat = self.repository.answered_count_per_pillar_category(
                    session.session_id
                )
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Pillar round-robin unavailable; using the category order",
                extra={"session_id": session.session_id},
            )
            return _sort_key

        if not problem_to_pillar:
            return _sort_key

        per_pillar: dict[int, int] = {}
        for (pillar_id, _category), count in per_cat.items():
            per_pillar[pillar_id] = per_pillar.get(pillar_id, 0) + count

        # THIRD term, and its position is the whole design. Industry decides
        # WHICH question represents a (pillar, category) in a round; the two
        # coverage terms above still decide how many rounds each pillar and each
        # category gets. Promote it above them and a well-stocked industry -- 60
        # seeded questions, all CORE -- would take rounds from pillars that have
        # not been asked about at all, which is the exact starvation this key was
        # written to stop. Demote it below `_sort_key` and it could never change
        # anything, because question_id is a total order.
        industry_rank = self._industry_rank_for(session, founder)

        def key(question: Question):
            pillar_id = problem_to_pillar.get(question.problem_id)
            # A question with no pillar cannot advance pillar coverage, so it
            # sorts behind every pillar-bearing question rather than competing
            # for a round it does not belong to.
            if pillar_id is None:
                return (len(per_pillar) + 1_000, 0,
                        industry_rank(question), *_sort_key(question))
            return (
                per_pillar.get(pillar_id, 0),
                per_cat.get((pillar_id, question.category), 0),
                industry_rank(question),
                *_sort_key(question),
            )

        return key

    def _industry_rank_for(
        self, session: DiagnosisSession, founder: Founder | None
    ):
        """`question -> relevance rank` for this founder's industry.

        Returns a CONSTANT ranker -- one that cannot reorder anything -- rather
        than raising, whenever the industry is unknown or any of the three reads
        fails. Twenty-six of the thirty industries carry no
        `top_pain_point_weights` today, so "no weight signal" is the ordinary
        state and not a fault; those founders still get the mapping signal, and
        a founder with neither gets exactly the pre-industry order.

        Same degrade contract as `_pillar_map_or_none` and
        `_detected_root_cause_ids`: a preference must never be able to stop the
        assessment from finding a next question.
        """
        industry_id = industry_id_for(session, founder)
        if industry_id is None:
            return relevance_ranker(None, None, None)

        try:
            with self.repository.db.begin_nested():
                code = self.repository.industry_code(industry_id)
                applicability = (
                    self.repository.question_applicability_for_industry(code)
                    if code else {}
                )
                weights = normalise_weights(
                    self.repository.industry_pain_point_weights(industry_id)
                )
                problem_to_code = self.repository.problem_to_code() if weights else {}
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Industry relevance unavailable; using the default order",
                extra={"stage": "industry_scope", "session_id": session.session_id},
            )
            return relevance_ranker(None, None, None)

        return relevance_ranker(applicability, problem_to_code, weights)

    def _sort_key_for(
        self, session: DiagnosisSession, founder: Founder | None = None
    ):
        """The ranking key, biased by what the session is currently trying to do.

        Below the validate threshold the job is to GATHER: cover all six
        pillars before deepening any of them. That is `_round_robin_key_for`.

        Between the validate and report thresholds the job changes to CONFIRMING.
        The diagnosis already has candidate root causes; asking more broad
        questions adds coverage but does not resolve which cause is real -- and
        confirmation and separation are 25% of the confidence score between them,
        neither of which broad questions move. So questions tied to an
        already-detected cause sort first, and the deterministic key orders within
        that group exactly as before.

        The bias only reorders. It never filters: every question stays reachable,
        so a session in validate mode that runs out of targeted questions simply
        continues with the normal order rather than ending early.
        """
        base = self._round_robin_key_for(session, founder)

        targeted = self._detected_root_cause_ids(session)
        if not targeted:
            return base

        # Confirmation outranks coverage once there is something to confirm --
        # but only among targeted questions. Everything below still round-robins,
        # so falling out of validate mode resumes even pillar coverage rather
        # than reverting to a single-category drain.
        def key(question: Question):
            confirms = question.root_cause_id in targeted
            return (0 if confirms else 1, *base(question))

        return key

    def _detected_root_cause_ids(self, session: DiagnosisSession) -> set[int]:
        """Root causes worth confirming, or empty when the bias does not apply.

        Empty unless the session is in VALIDATE: in CONTINUE there is not yet a
        picture to confirm, and in GENERATE_REPORT the diagnosis is over.
        """
        if session.routing_state != RoutingState.VALIDATE.value:
            return set()
        try:
            with self.repository.db.begin_nested():
                return self.repository.get_detected_root_cause_ids(session.session_id)
        except Exception:                                  # noqa: BLE001
            # Question selection must never fail on an optional preference.
            logger.warning("Validate-mode bias unavailable; using the default order",
                           extra={"session_id": session.session_id})
            return set()

    def candidate_questions(
        self, session: DiagnosisSession, founder: Founder
    ) -> list[Question]:
        """Unanswered, stage-eligible, in-scope questions for this session.

        Two independent stage filters apply, and both are needed. The repository
        filters on `primary_stage_group`, which decides how a question is WORDED
        for this founder. `_in_scope` then filters on pillar, which decides which
        SUBJECTS may be raised at all. A Team & Leadership question written for
        Stage 0 passes the first and fails the second.
        """
        candidates = self.repository.list_candidate_questions(
            session_id=session.session_id,
            stage_groups=resolve_stage_groups(founder),
            # Lets the repository drop questions this founder already answered
            # verbatim during Founder DNA -- see list_candidate_questions.
            founder_id=founder.founder_id,
        )
        return self._in_scope(candidates, founder, session)

    def _in_scope(
        self,
        candidates: list[Question],
        founder: Founder,
        session: DiagnosisSession | None = None,
    ) -> list[Question]:
        """Drop questions this founder should not be asked.

        CONTEXT runs first and is a different axis from the rest: it asks
        whether the subject is part of the founder's situation at all, not
        whether they are far enough along to have an answer. It applies at every
        stage, including the ones that withhold nothing. See `context_scope`.

        Then two independent tests, both derived from the same Part 3 dimension
        set (see `stage_scope`), and both applied:

          PILLAR    which subjects may be raised at all, read through
                    problems.pillar_id.
          CATEGORY  what the question is actually about, read straight off
                    questions.category.

        The second is not implied by the first. Marketing Execution questions
        are filed under Market Clarity, which Part 3 puts fully in scope at
        ideation -- so pillar scope alone admits campaign-attribution questions
        to a founder with nothing built. Category scope is what makes "no
        revenue and no marketing questions before there is a business" a rule
        rather than an accident of how the Stage 0 bank happens to be tagged
        today.

        Filtering here rather than in the ranking key is deliberate. The bias in
        `_sort_key_for` only reorders, so an out-of-scope question would still be
        asked once the in-scope ones ran out -- which is exactly the budget-tail
        case an ideation founder hits. Scope is a rule about what may be asked,
        not a preference about what to ask first, so it removes candidates.

        The two tests DEGRADE INDEPENDENTLY. The pillar test needs a database
        lookup and the category test does not, so an unavailable pillar map
        drops the pillar test and keeps the category one, rather than
        abandoning both and handing an ideation founder the whole bank.

        Never returns empty when it was given a non-empty set. A scope that
        matches nothing means the bank and the scope table disagree, and ending
        a founder's diagnosis early over a data problem is worse than asking a
        question that is off-topic for their stage. Same reasoning as the
        round-robin's degrade path: correctness of coverage must never be able to
        stop the assessment from finding a next question.
        """
        if not candidates:
            return candidates

        # CONTEXT first, and OUTSIDE the stage-scope short-circuit below. It is
        # a different axis and must survive `withholds_nothing`, which is true
        # from Growth onward -- a scaling founder who is not raising is not too
        # early for fundraising questions, the subject is simply not theirs.
        # Rebinding `candidates` is deliberate: the stage-scope fallback further
        # down returns this name, so a stage-scope data problem re-admits the
        # stage filters and never re-admits a gated problem.
        candidates = self._context_gated(candidates, founder)

        # INDUSTRY next, and also outside the stage-scope short-circuit: a
        # question written for another industry is not something a Growth-stage
        # founder has merely outgrown, it was never theirs. Rebinding
        # `candidates` for the same reason `_context_gated` does -- the
        # stage-scope fallback below returns this name, so a stage-scope data
        # problem must not re-admit another industry's bank.
        candidates = self._industry_gated(candidates, founder, session)

        scope = resolve_scope(founder)
        if scope is None or scope.withholds_nothing:
            return candidates

        scoped = candidates
        applied: list[str] = []

        if scope.withheld_categories:
            scoped = [q for q in scoped if q.category not in scope.withheld_categories]
            applied.append("category")

        if not scope.covers_all_pillars:
            problem_to_pillar = self._pillar_map_or_none(scope)
            if problem_to_pillar:
                scoped = [
                    q for q in scoped
                    if problem_to_pillar.get(q.problem_id) in scope.pillars
                ]
                applied.append("pillar")

        if scope.excluded_dimensions:
            problem_to_dimension = self._dimension_map_or_none(scope)
            if problem_to_dimension:
                # `.get() not in` and not `.get() in scope.dimensions`: a
                # problem with no dimension recorded is UNKNOWN, not
                # out of scope, and most of the catalogue is unknown. Dropping
                # those would empty the candidate set at every stage and hand
                # the whole bank straight back through the fallback below --
                # scoping nothing while looking like it scoped everything.
                scoped = [
                    q for q in scoped
                    if problem_to_dimension.get(q.problem_id)
                    not in scope.excluded_dimensions
                ]
                applied.append("dimension")

        if not applied:
            return candidates

        if not scoped:
            logger.warning(
                "Stage scope matched no candidate question; leaving the set "
                "unscoped rather than ending the diagnosis",
                extra={
                    "stage_scope": scope.label,
                    "filters_applied": applied,
                    "candidates": len(candidates),
                },
            )
            return candidates

        logger.info(
            "diagnosis scoped to stage",
            extra={
                "stage": "stage_scope",
                "stage_scope": scope.label,
                "filters_applied": applied,
                "pillars_in_scope": sorted(scope.pillars),
                "categories_withheld": sorted(scope.withheld_categories),
                "dimensions_withheld": sorted(scope.excluded_dimensions),
                "candidates_before": len(candidates),
                "candidates_after": len(scoped),
            },
        )
        return scoped

    def _context_gated(
        self, candidates: list[Question], founder: Founder
    ) -> list[Question]:
        """Drop questions whose problem presupposes something this founder
        has not told us is true. See `context_scope`.

        Degrades the same way the pillar and dimension tests do, and for the
        same reason: an unavailable problem-code map disables THIS test only,
        rather than the whole of scoping. Three separate ways to end up not
        gating -- unknown context, unavailable map, or a gate that would empty
        the set -- and all three admit the question rather than withholding it.

        Never returns empty when it was given a non-empty set. Identical
        invariant to `_in_scope`'s, restated here because this filter runs
        before it and would otherwise hand it nothing to work with.
        """
        tokens = context_tokens(founder)
        gated = gated_problem_codes(tokens)
        gated_causes = gated_root_cause_codes(tokens)
        if not gated and not gated_causes:
            return candidates

        problem_to_code = self._code_map_or_none()
        if not problem_to_code:
            return candidates
        # Root-cause codes are only needed for the narrower gate; an unavailable
        # map disables that half and leaves the problem gate working.
        cause_to_code = self._cause_code_map_or_none() if gated_causes else {}

        # `.get() not in gated`: a problem or cause with no code recorded is
        # UNKNOWN and is admitted. Same reading as the dimension test -- absence
        # of a fact is never evidence for withholding.
        kept = [
            q for q in candidates
            if problem_to_code.get(q.problem_id) not in gated
            and cause_to_code.get(getattr(q, "root_cause_id", None)) not in gated_causes
        ]

        if not kept:
            logger.warning(
                "Context gate matched no candidate question; leaving the set "
                "ungated rather than ending the diagnosis",
                extra={
                    "stage": "context_scope",
                    "gated_problems": sorted(gated),
                    "candidates": len(candidates),
                },
            )
            return candidates

        if len(kept) != len(candidates):
            logger.info(
                "diagnosis gated on founder context",
                extra={
                    "stage": "context_scope",
                    "gated_problems": sorted(gated),
                    "withheld": len(candidates) - len(kept),
                    "candidates": len(candidates),
                },
            )
        return kept

    def _industry_gated(
        self,
        candidates: list[Question],
        founder: Founder,
        session: DiagnosisSession | None,
    ) -> list[Question]:
        """Drop questions written for an industry that is not this founder's.

        See `industry_scope` for why this is needed at all -- in short, 1,800
        seeded industry questions are stage-tagged and therefore eligible for
        every founder, so a Logistics founder is today a valid candidate for a
        SaaS security-certification question.

        Degrades exactly like `_context_gated` and the pillar and dimension
        tests, and for the same reason: an unavailable mapping table disables
        THIS test only. Four separate ways to end up not gating -- no mapping
        rows, an unreadable mapping table, an unreadable industry code, or a
        gate that would empty the set -- and every one of them admits the
        question rather than withholding it.

        Never returns empty when it was given a non-empty set. Same invariant as
        `_in_scope` and `_context_gated`: ending a founder's diagnosis early over
        a data problem is worse than asking one off-industry question.
        """
        if not candidates:
            return candidates

        owned = self._industry_ownership_or_none()
        if not owned:
            return candidates

        industry_id = industry_id_for(session, founder)
        # A missing industry is not a missing MAP: `excluded_question_ids`
        # treats an unknown industry as "no industry's questions are yours",
        # which leaves the whole universal bank reachable. See its docstring for
        # why that is the right direction here and not a failure to fail open.
        code = self._industry_code_or_none(industry_id) if industry_id else None
        excluded = excluded_question_ids(owned, code)
        if not excluded:
            return candidates

        kept = [q for q in candidates if q.question_id not in excluded]

        if not kept:
            logger.warning(
                "Industry gate matched no candidate question; leaving the set "
                "ungated rather than ending the diagnosis",
                extra={
                    "stage": "industry_scope",
                    "industry_code": code,
                    "candidates": len(candidates),
                },
            )
            return candidates

        if len(kept) != len(candidates):
            logger.info(
                "diagnosis gated on founder industry",
                extra={
                    "stage": "industry_scope",
                    "industry_code": code,
                    "withheld": len(candidates) - len(kept),
                    "candidates": len(candidates),
                },
            )
        return kept

    def _industry_ownership_or_none(self) -> dict[int, frozenset[str]] | None:
        """{question_id: {industry_code}} for industry-owned questions, or None
        when the mapping table cannot be read.

        Empty is treated the same as unavailable, and here that is an ordinary
        state rather than a fault: a database where the industry seeds have not
        been applied has no mapping rows and no industry questions either, so
        there is nothing to gate. Mirrors `_dimension_map_or_none`.
        """
        try:
            with self.repository.db.begin_nested():
                owned = self.repository.question_owned_by_industry()
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Industry mapping unavailable; selecting without the industry gate",
                extra={"stage": "industry_scope"},
            )
            return None
        return owned or None

    def _industry_code_or_none(self, industry_id: int) -> str | None:
        """`industries.industry_code` for this founder, or None when unreadable.

        None here means UNKNOWN INDUSTRY, which the gate handles deliberately
        (no industry's questions are this founder's) rather than by disabling
        itself -- disabling would re-admit all thirty industries at once, which
        is the very thing the gate exists to stop.
        """
        try:
            with self.repository.db.begin_nested():
                return self.repository.industry_code(industry_id)
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Industry code unreadable; gating as unknown industry",
                extra={"stage": "industry_scope", "industry_id": industry_id},
            )
            return None

    def _cause_code_map_or_none(self) -> dict[int, str]:
        """root_cause_id -> root_cause_code, or {} when it cannot be read.

        Empty rather than None: the caller uses it in a membership test, and an
        empty map admits everything, which is the fail-open direction.
        """
        try:
            with self.repository.db.begin_nested():
                return self.repository.root_cause_to_code()
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Root-cause code map unavailable; gating problems only",
                extra={"stage": "context_scope"},
            )
            return {}

    def _code_map_or_none(self) -> dict[int, str] | None:
        """problem_id -> problem_code, or None when the context gate cannot run.

        Mirrors `_pillar_map_or_none`, including the nested transaction, so a
        failed lookup cannot poison the session the caller is inside.
        """
        try:
            with self.repository.db.begin_nested():
                return self.repository.problem_to_code()
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Problem-code map unavailable; selecting without the context gate",
                extra={"stage": "context_scope"},
            )
            return None

    def _pillar_map_or_none(self, scope) -> dict[int, int] | None:
        """problem_id -> pillar_id, or None when the pillar test cannot run.

        Separate from `_in_scope` so an unavailable map disables only the pillar
        part of scoping. Returning None where this used to return the whole
        candidate list is the difference between "we cannot check pillars" and
        "we cannot check anything".
        """
        try:
            with self.repository.db.begin_nested():
                problem_to_pillar = self.repository.problem_to_pillar()
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Pillar map unavailable; scoping this stage without it",
                extra={"stage_scope": scope.label},
            )
            return None
        return problem_to_pillar or None

    def _dimension_map_or_none(self, scope) -> dict[int, str] | None:
        """problem_id -> dimension_code, or None when that test cannot run.

        Empty is treated the same as unavailable, and here that is the ordinary
        case rather than a fault: until the catalogue is mapped there is nothing
        to filter on, and the two coarser tests carry the scope on their own.
        Logged at debug rather than warning for exactly that reason -- a warning
        on every question of every session would say nothing.
        """
        try:
            with self.repository.db.begin_nested():
                problem_to_dimension = self.repository.problem_to_dimension()
        except Exception:                                  # noqa: BLE001
            logger.warning(
                "Dimension map unavailable; scoping this stage without it",
                extra={"stage_scope": scope.label},
            )
            return None
        return problem_to_dimension or None

    def order_candidates(
        self,
        candidates: list[Question],
        session: DiagnosisSession | None = None,
        founder: Founder | None = None,
    ) -> list[Question]:
        """The deterministic ask-order -- the shortlist head is the default pick.

        Takes the session so the adaptive advisor's shortlist carries the same
        validate-mode bias as the direct pick; without it the LLM would be handed
        a broad shortlist while the deterministic path was targeting confirmation.

        Takes the founder for the same reason, one axis over: the shortlist must
        carry the same INDUSTRY bias too. The session's snapshot is normally
        enough on its own (`start_session` writes it), so the founder is optional
        and is only the fallback for a session that predates the snapshot.
        """
        key = (
            self._sort_key_for(session, founder) if session is not None else _sort_key
        )
        return sorted(candidates, key=key)

    def resolve_follow_up(self, session: DiagnosisSession, answer_question: Question) -> None:
        """Follow-up hook -- inert until scoring exists.

        `questions.follow_up_question_id` defines WHICH question follows, but
        whether to branch depends on the answer scoring red vs green. Returning
        None keeps the flow linear; wire this up alongside the scoring engine.
        """
        return None
