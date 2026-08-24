"""Founder DNA question-selection engine.

Ordering is the doc's narrative arc, not round-robin. An earlier cut of this
engine round-robined by least-answered dimension -- correct as a reaction to
the bug that started this work (the diagnosis engine exhausting one category
before starting the next, so a 30-question budget never reached Business DNA),
but wrong for this phase: `GoXL_Founder_DNA_Decoding_Journey.docx` Section 3
specifies a deliberate arc, "opens wide and emotional (identity, origin)
before narrowing into structured territory (decision style, values)", and
round-robin scrambles it.

Breadth is preserved a different way, so the original bug cannot come back:
a dimension is only ever skipped AFTER it has been asked at least once and
judged resolved, so the BASE journey (arc_position < 90) still reaches every
dimension by construction rather than by the selection order happening to
interleave.

Within that guarantee, adaptive skipping applies to base questions and
follow-ups alike -- which is what the doc asks for, "if an answer already
resolves a dimension with high confidence, the next scripted question for
that dimension is skipped". An earlier cut confined skipping to follow-ups
(arc_position >= 90) and made base questions unconditional; the effect was
that for the first nine turns a founder's answers could not influence the
next question at all, while the screen said "Adaptive diagnosis".

Shape per stage: 9 base + up to 2 follow-ups + 1 closing = 10-12 asked.

The closing question (`is_closing`, the doc's "wow close") is held back and
always asked last, even when the ceiling cuts the journey short -- a journey
that ends mid-probe has no ending, which is the one thing the doc is
explicit about not wanting.

Stage-group resolution reuses app.api.v1.diagnosis.engine's mapping (same
founder, same three groups) rather than duplicating it.
"""

from __future__ import annotations

from app.api.v1.diagnosis.engine import resolve_stage_groups
from app.api.v1.founder_dna.repository import FounderDnaRepository
from app.core.config import settings
from app.models import StageGroup
from app.models.schema import FounderDnaQuestions, Founders

#: Every dimension the phase asks about, in the doc's Section 2 order. Kept
#: as a literal tuple rather than derived from FounderDnaDimension so the
#: ORDER is explicit here -- it is the fallback ordering when two questions
#: share an arc_position, and reordering an enum by accident should not
#: silently reorder a founder's journey.
ALL_DIMENSIONS: tuple[str, ...] = (
    "archetype", "core_motivation", "origin", "purpose_mission", "vision",
    "core_values", "mindset_excellence", "strengths_blind_spots",
    "energy_patterns", "stress_response", "decision_style",
    "communication_preference", "focus_attention", "emotional_intelligence",
)

#: arc_position at/above which a question is an adaptive FOLLOW-UP rather than
#: part of the mandatory base journey. Keeps the two in one ordered column
#: instead of a second boolean that could disagree with it.
FOLLOW_UP_FLOOR = 90

#: The group a founder whose stage is NOT recorded is asked against.
#:
#: Stated as a named constant rather than falling out of `StageGroup`'s member
#: order, which is what this used to do -- see resolve_founder_dna_stage_group.
#: Reordering that enum must not silently rewrite which questions an
#: unknown-stage founder is asked.
#:
#: Stage 0→1 (Validation, Prototype/MVP, Early Traction) rather than Stage 0
#: (Ideation alone), for two reasons. It is the modal band -- three of the
#: eight founder_stages sit in it, and it is where a founder who has come
#: looking for a diagnosis of what is blocking them usually is. And it bounds
#: the error: from the middle band the guess is at most one band out in either
#: direction, where Stage 0 can be three stages short.
#:
#: The asymmetry matters more than the arithmetic. Asking a founder who has
#: shipped an MVP "what is standing between you and actually starting" is not
#: a slightly-off question, it is a statement that the product has not read
#: anything they said -- observed live, to a founder with a working MVP and
#: three running pilots. Asking a genuine ideation founder a validation-shaped
#: question is merely early.
#:
#: This is still a guess. The real fix is to record the stage: it is collected
#: only in guided onboarding (frontend/src/pages/guided/ProfileBuild.jsx), and
#: a founder who reaches the app without completing that step has no way to set
#: it afterwards -- /app/profile shows stage in its completeness ring but
#: offers no field for it. Until that gap closes, this constant decides what
#: every such founder is asked.
UNKNOWN_STAGE_DEFAULT_GROUP: str = StageGroup.STAGE_0_TO_1.value


def resolve_founder_dna_stage_group(founder: Founders) -> str:
    """The single stage group to ask this founder against.

    Founder DNA and Current Problem questions are authored per SINGLE stage
    group (unlike the diagnosis bank, whose primary_stage_group also allows a
    stage-agnostic NULL), so this must resolve to exactly one -- both phases
    query `stage_group == <this>`.

    resolve_stage_groups returns exactly one group for a founder whose stage
    is known, and deliberately FAILS OPEN to every group for one whose stage
    is not recorded ("the same 'we don't actually know' situation as no stage
    at all -- fail open to every group rather than raise"). More than one
    group back is therefore precisely the signal that the stage is unknown,
    which is why that is what this branches on: it carries the same meaning
    regardless of how StageGroup happens to be ordered.

    Taking `groups[0]`, as this used to, threw that signal away. The fail-open
    list is built by iterating StageGroup, whose first member is STAGE_0, so
    every unknown-stage founder was silently pinned to pure ideation -- for
    the whole of Founder DNA AND Current Problem, since both resolve through
    here. The docstring already claimed to "default to the group most founders
    starting this phase are in"; the code defaulted to whichever group the enum
    listed first, and nothing tied the two together.
    """
    groups = resolve_stage_groups(founder)
    if len(groups) == 1:
        return groups[0]
    return UNKNOWN_STAGE_DEFAULT_GROUP


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
        """Next question along the doc's arc, or the closing question when the
        journey is otherwise done. None only when even that is answered.

        Order of precedence:
          1. BASE questions (arc_position < FOLLOW_UP_FLOOR), by arc_position,
             skipping dimensions the advisor has resolved -- but never one
             that has not been asked yet, so the arc still visits every
             dimension.
          2. FOLLOW-UPS, by arc_position, only for dimensions the advisor has
             NOT resolved, and only while the budget leaves room for the
             closing question.
          3. The closing question, always last.
        """
        # The close is TERMINAL, not merely last-sorted. Once it has been asked
        # the journey is over, even if the budget would still afford another
        # follow-up.
        #
        # Ordering used to fall out of budget exhaustion alone -- `closing` was
        # returned only when no slot remained -- which held only because the
        # ceiling happened to be exactly base + 1 + close. The moment there was
        # any headroom, the close fired while follow-ups were still pending and
        # one landed AFTER it. Verified live: Q16 was the close, Q17 an
        # energy_patterns follow-up. Ending on an analytical question instead of
        # the wow-close is precisely what this ordering exists to prevent, so it
        # is now stated directly rather than being an emergent property of
        # arithmetic elsewhere.
        if self.repository.closing_answered(founder.founder_id, stage_group):
            return None

        candidates = self.candidate_questions(founder, stage_group)
        if not candidates:
            return None

        closing = next((q for q in candidates if q.is_closing), None)
        pending = [q for q in candidates if not q.is_closing]
        resolved = self.repository.get_resolved_dimensions(founder)
        asked_per_dimension = self.repository.answers_per_dimension(
            founder.founder_id, stage_group
        )

        base = [q for q in pending if q.arc_position < FOLLOW_UP_FLOOR]
        if base:
            # Adaptive skipping applies to the BASE journey too, not only to
            # follow-ups. Live testing found the opposite reading of "base is
            # mandatory" -- which this engine used to implement -- meant a
            # founder's answers could not affect the next question at all for
            # the first nine turns. Whatever they wrote, the same scripted
            # question came back, which is exactly what "Adaptive diagnosis"
            # on the screen promises it is not doing.
            #
            # Breadth, which mandatory-base existed to guarantee, is preserved
            # by the `asked_per_dimension` condition rather than by refusing to
            # skip: a dimension is only ever skipped once it has ALREADY been
            # asked at least once and the advisor has judged it resolved. So
            # every dimension still gets its first base question by
            # construction, and the original bug (a phase ending with
            # dimensions never touched) cannot come back.
            #
            # The arc is preserved because this filters, never reorders --
            # what survives is still taken in arc_position order.
            unresolved_base = [
                q for q in base
                if q.dimension_code not in resolved
                or asked_per_dimension.get(q.dimension_code, 0) == 0
            ]
            if unresolved_base:
                return min(
                    unresolved_base,
                    key=lambda q: (q.arc_position, q.founder_dna_question_id),
                )
            # Every remaining base question belongs to an already-resolved
            # dimension. Falling through to follow-ups/close is correct: there
            # is nothing left worth asking, which is what "adaptive" means.

        # Base journey done -- follow-ups only where a dimension is still open,
        # and only if answering one still leaves the closing slot affordable.
        answered = self.repository.count_answered(founder.founder_id)
        closing_reserve = 1 if closing is not None else 0
        if answered + closing_reserve < settings.MAX_FOUNDER_DNA_QUESTIONS:
            follow_ups = [q for q in pending if q.dimension_code not in resolved]
            if follow_ups:
                # Fewest-asked dimension first, THEN arc_position.
                #
                # Ordering by arc_position alone let one stubborn low-arc
                # dimension monopolise a budget that is already tight: 14
                # dimensions against MAX_FOUNDER_DNA_QUESTIONS=16. Observed
                # live -- `purpose_mission` took three follow-up slots while
                # `core_values` and `energy_patterns` were never asked a second
                # time, and the phase then closed reporting 12 of 14 resolved
                # with those two blank forever.
                #
                # Every remaining question here belongs to an UNRESOLVED
                # dimension, so they are all equally deserving; spreading the
                # scarce slots across them resolves strictly more dimensions
                # than spending them all on whichever one sorts first.
                # arc_position stays the tiebreaker, so authored order still
                # decides between dimensions that have had equal attention.
                return min(
                    follow_ups,
                    key=lambda q: (
                        asked_per_dimension.get(q.dimension_code, 0),
                        q.arc_position,
                        q.founder_dna_question_id,
                    ),
                )

        return closing

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
        """Complete only when there is genuinely nothing left to ask.

        Deliberately NOT "all dimensions resolved" or "budget spent" as
        standalone conditions any more, which is what an earlier cut used:
        both could fire while the closing question was still unanswered, and
        ending the journey without its close is precisely what the doc's "wow
        close" principle rules out. select_next_question() already reserves a
        slot for the close and returns it last, so deferring to it keeps one
        definition of "done" instead of two that can disagree.
        """
        return self.select_next_question(founder, stage_group) is None
