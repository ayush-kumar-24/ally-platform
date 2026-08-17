"""Founder DNA question-selection engine.

This is the actual fix for the bug that started this work: the existing
diagnosis engine (app/api/v1/diagnosis/engine.py) walks one category to
exhaustion before starting the next (CATEGORY_SEQUENCE), which is why a
30-question budget never reached Business DNA. This engine round-robins
across dimensions instead -- the least-answered still-open dimension goes
next, every time -- so a founder always gets breadth across all 6 dimensions
before depth in any one, and a session cut short by the safety ceiling still
has partial signal on every dimension rather than zero signal on five of them.

Stage-group resolution reuses app.api.v1.diagnosis.engine's mapping (same
founder, same three groups) rather than duplicating it.
"""

from __future__ import annotations

from app.api.v1.diagnosis.engine import resolve_stage_groups
from app.api.v1.founder_dna.repository import FounderDnaRepository
from app.core.config import settings
from app.models.schema import FounderDnaQuestions, Founders

ALL_DIMENSIONS: tuple[str, ...] = (
    "purpose_mission", "core_values", "mindset_excellence",
    "energy_patterns", "decision_style", "focus_attention",
)


def resolve_founder_dna_stage_group(founder: Founders) -> str:
    """Founder DNA questions are authored per SINGLE stage group (unlike the
    diagnosis bank, whose primary_stage_group also allows a stage-agnostic
    NULL) -- resolve_stage_groups always returns exactly one group unless
    the founder's stage is unset, in which case default to the group most
    founders starting this phase are in.
    """
    groups = resolve_stage_groups(founder)
    return groups[0] if groups else "Stage 0"


class FounderDnaSelectionEngine:
    def __init__(self, repository: FounderDnaRepository):
        self.repository = repository

    def candidate_questions(
        self, founder: Founders, stage_group: str
    ) -> list[FounderDnaQuestions]:
        return self.repository.list_candidate_questions(founder.founder_id, stage_group)

    def select_next_question(
        self, founder: Founders, stage_group: str
    ) -> FounderDnaQuestions | None:
        """Round-robin across dimensions NOT yet resolved: the dimension with
        the fewest answers so far (ties broken by dimension order, then
        question id) goes next. A resolved dimension is skipped even if its
        pool has unanswered questions left -- that's the whole point of
        "adaptive": more signal on a settled dimension doesn't help.
        """
        resolved = self.repository.get_resolved_dimensions(founder)
        candidates = [
            q for q in self.candidate_questions(founder, stage_group)
            if q.dimension_code not in resolved
        ]
        if not candidates:
            return None

        answered_counts = self.repository.answers_per_dimension(
            founder.founder_id, stage_group
        )
        return min(
            candidates,
            key=lambda q: (
                answered_counts.get(q.dimension_code, 0),
                ALL_DIMENSIONS.index(q.dimension_code)
                if q.dimension_code in ALL_DIMENSIONS else len(ALL_DIMENSIONS),
                q.founder_dna_question_id,
            ),
        )

    def dimension_pool_exhausted(
        self, founder: Founders, dimension_code: str, stage_group: str
    ) -> bool:
        """True once every active question for this dimension+stage has been
        answered -- the deterministic fallback stop when the (optional) LLM
        resolution advisor is off, errors, or never fires."""
        answered = self.repository.answers_per_dimension(founder.founder_id, stage_group)
        pool = self.repository.pool_size_per_dimension(stage_group)
        return answered.get(dimension_code, 0) >= pool.get(dimension_code, 0)

    def is_phase_complete(self, founder: Founders, stage_group: str) -> bool:
        resolved = self.repository.get_resolved_dimensions(founder)
        if set(ALL_DIMENSIONS) <= resolved:
            return True
        if self.repository.count_answered(founder.founder_id) >= settings.MAX_FOUNDER_DNA_QUESTIONS:
            return True
        return self.select_next_question(founder, stage_group) is None
