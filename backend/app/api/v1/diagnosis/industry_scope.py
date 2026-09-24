"""Whose questions a founder may be asked.

A FOURTH AXIS, separate from the three already applied in `stage_scope` and
`context_scope`. Stage scope answers "is this founder far enough along to have
an answer?"; context scope answers "is this subject part of their situation at
all?"; this answers "was this question written for somebody else's industry?".

WHAT WENT WRONG WITHOUT IT. Thirty industry datasets are seeded -- 60 questions
each, 1,800 in total (migrations `91c4f0a2bd73_seed_twelve_industry_datasets`
and `*_seed_industry_batch_[a-e]`). Every one of them carries a real
`primary_stage_group`, so every one of them is a fully eligible candidate for
every founder, because `list_candidate_questions` filters on stage group and
nothing else. Measured on the seeded bank: a Logistics founder at Stage 1->10+
is eligible for `S10-SAS-011` "Do you have any security certification buyers
recognise?", and a SaaS founder for `S01-LOG-002` "Out of 100 deliveries, how
many arrive damaged?".

They are not asked constantly today only because the industry rows were inserted
late and therefore carry high `question_id`s, which lose the final tie-break in
`engine._sort_key`. That is an accident of insertion order, not a rule, and a
reseed or a budget change undoes it.

THE LINK ALREADY EXISTS. `question_industry_mapping` (created by migration
`62ebd946ebc0_industry_stage_structure`) holds exactly the fact this module
needs, and every industry seed populates it -- 60 rows per industry, asserted at
migration time. Its own table comment states the intended reading:

    'Links a question to a specific industry + stage. A question with no row
     here is treated as universal (applies everywhere).'

Nothing in `backend/app/` read it until now. This module is that read.

WHAT THIS IS NOT. It is not a whitelist and it must never become one. It removes
another industry's questions; it never removes a universal one, and it never
promotes anything. Promotion is a ranking concern and belongs in
`engine._round_robin_key_for`, below pillar coverage, so that industry can
decide WHICH question fills a pillar's turn but never how many turns a pillar
gets. Keeping the two apart is what stops "relevant to your industry" from
quietly becoming "only your industry", which would make most of the catalogue
unreachable.
"""

from __future__ import annotations

from typing import Any

from app.core.logger import logger


def industry_id_for(session: Any, founder: Any) -> int | None:
    """The industry this diagnosis is being run for, or None when unknown.

    Session first, founder second -- the same precedence
    `reasoning/service.py:936` uses, so selection and reasoning can never
    disagree about which industry's dataset a session belongs to.

    Reading the session's snapshot rather than the founder's live column is what
    keeps a running session isolated: a founder who edits their industry halfway
    through a diagnosis does not silently change which questions the remaining
    turns are drawn from. `service.start_session` writes the snapshot
    (`sessions.founder_industry_id`) when the session is created.

    Never raises. An unreadable profile must never be able to end a diagnosis.
    """
    try:
        from_session = getattr(session, "founder_industry_id", None)
        if from_session is not None:
            return int(from_session)
        from_founder = getattr(founder, "industry_mapped_id", None)
        return int(from_founder) if from_founder is not None else None
    except (TypeError, ValueError):                        # noqa: BLE001
        logger.warning(
            "Industry id unreadable; industry gate fails open",
            extra={"stage": "industry_scope"},
        )
        return None


def excluded_question_ids(
    owned_by_industry: dict[int, frozenset[str]] | None,
    industry_code: str | None,
) -> frozenset[int]:
    """Question ids written for an industry that is not this founder's.

    `owned_by_industry` is {question_id: {industry_code, ...}} for questions that
    have at least one `question_industry_mapping` row. A question absent from it
    is universal and is never excluded -- that is the table comment's rule, and
    it is why this cannot shrink the general bank.

    UNKNOWN INDUSTRY EXCLUDES EVERY INDUSTRY-OWNED QUESTION, which is the one
    place this module does not fail open in the usual direction, and it is
    deliberate. The alternative reading -- "we do not know their industry, so
    admit all thirty industries' questions" -- is not neutral: it is the current
    bug, and it means a founder who skipped the industry question is the ONLY
    founder who can be asked about crop yields and delivery damage in the same
    sitting. Excluding them all leaves the entire universal bank (the large
    majority of the catalogue) reachable, so there is no starvation risk, and
    `engine._industry_gated` still refuses to return an empty set.

    Pure and side-effect free: no database, no session, so the rule is
    unit-testable on a dict.
    """
    if not owned_by_industry:
        return frozenset()
    if not industry_code:
        return frozenset(owned_by_industry)
    wanted = industry_code.strip().casefold()
    return frozenset(
        question_id
        for question_id, industries in owned_by_industry.items()
        if not any(code.strip().casefold() == wanted for code in industries)
    )
