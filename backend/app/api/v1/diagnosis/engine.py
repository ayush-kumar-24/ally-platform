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
from app.models import DiagnosisSession, Founder, Question, QuestionPriority, StageGroup

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
# ASSUMPTION -- please confirm.
#
# `questions.primary_stage_group` buckets questions into three groups, but no
# column anywhere links a founder's stage (founder_stages.stage_id, 1..8) to
# those buckets. This mapping is therefore a business rule with no database
# backing, derived from stage_order:
#
#     Ideation(1), Validation(2)          -> Stage 0
#     Prototype/MVP(3), Early Traction(4) -> Stage 0->1
#     Growth(5) .. Exit(8)                -> Stage 1->10+
#
# If the intended boundaries differ, this constant is the only thing to change.
# ---------------------------------------------------------------------------
_STAGE_ORDER_TO_GROUP: tuple[tuple[int, StageGroup], ...] = (
    (2, StageGroup.STAGE_0),
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
        return min(candidates, key=_sort_key)

    def candidate_questions(
        self, session: DiagnosisSession, founder: Founder
    ) -> list[Question]:
        """Unanswered, stage-eligible questions for this session (unordered)."""
        return self.repository.list_candidate_questions(
            session_id=session.session_id,
            stage_groups=resolve_stage_groups(founder),
        )

    @staticmethod
    def order_candidates(candidates: list[Question]) -> list[Question]:
        """The deterministic ask-order -- the shortlist head is the default pick."""
        return sorted(candidates, key=_sort_key)

    def resolve_follow_up(self, session: DiagnosisSession, answer_question: Question) -> None:
        """Follow-up hook -- inert until scoring exists.

        `questions.follow_up_question_id` defines WHICH question follows, but
        whether to branch depends on the answer scoring red vs green. Returning
        None keeps the flow linear; wire this up alongside the scoring engine.
        """
        return None
