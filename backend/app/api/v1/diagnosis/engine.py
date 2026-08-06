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

from app.api.v1.diagnosis.repository import DiagnosisRepository
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
    stage = founder.stage
    if stage is None:
        return [group.value for group in StageGroup]

    for max_order, group in _STAGE_ORDER_TO_GROUP:
        if stage.stage_order <= max_order:
            return [group.value]

    return [StageGroup.STAGE_1_TO_10_PLUS.value]


def _sort_key(question: Question) -> tuple[int, int, int, int]:
    """Deterministic ranking key.

    Category sequence, then CORE before SUPPLEMENTARY, then easiest first so
    the founder warms up before the harder probes, then question_id purely as a
    tie-breaker so the order can never wobble between requests.

    A category outside CATEGORY_SEQUENCE sorts last rather than raising -- a
    newly seeded category should degrade to "asked late", not break the
    assessment.
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
        return min(candidates, key=self._sort_key_for(session))

    def _sort_key_for(self, session: DiagnosisSession):
        """The ranking key, biased by what the session is currently trying to do.

        Below the validate threshold the job is to GATHER: sweep the categories in
        sequence and build a picture. That is `_sort_key`, unchanged.

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
        targeted = self._detected_root_cause_ids(session)
        if not targeted:
            return _sort_key

        def key(question: Question):
            confirms = question.root_cause_id in targeted
            return (0 if confirms else 1, *_sort_key(question))

        return key

    def _detected_root_cause_ids(self, session: DiagnosisSession) -> set[int]:
        """Root causes worth confirming, or empty when the bias does not apply.

        Empty unless the session is in VALIDATE: in CONTINUE there is not yet a
        picture to confirm, and in GENERATE_REPORT the diagnosis is over.
        """
        if session.routing_state != RoutingState.VALIDATE.value:
            return set()
        try:
            return self.repository.get_detected_root_cause_ids(session.session_id)
        except Exception:                                  # noqa: BLE001
            # Question selection must never fail on an optional preference.
            logger.warning("Validate-mode bias unavailable; using the default order",
                           extra={"session_id": session.session_id})
            return set()

    def candidate_questions(
        self, session: DiagnosisSession, founder: Founder
    ) -> list[Question]:
        """Unanswered, stage-eligible questions for this session (unordered)."""
        return self.repository.list_candidate_questions(
            session_id=session.session_id,
            stage_groups=resolve_stage_groups(founder),
        )

    def order_candidates(
        self, candidates: list[Question], session: DiagnosisSession | None = None
    ) -> list[Question]:
        """The deterministic ask-order -- the shortlist head is the default pick.

        Takes the session so the adaptive advisor's shortlist carries the same
        validate-mode bias as the direct pick; without it the LLM would be handed
        a broad shortlist while the deterministic path was targeting confirmation.
        """
        key = self._sort_key_for(session) if session is not None else _sort_key
        return sorted(candidates, key=key)

    def resolve_follow_up(self, session: DiagnosisSession, answer_question: Question) -> None:
        """Follow-up hook -- inert until scoring exists.

        `questions.follow_up_question_id` defines WHICH question follows, but
        whether to branch depends on the answer scoring red vs green. Returning
        None keeps the flow linear; wire this up alongside the scoring engine.
        """
        return None
