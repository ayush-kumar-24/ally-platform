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

from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from app.core.logger import logger

# --- Relevance ranks -------------------------------------------------------
#
# Lower sorts first. These are a PREFERENCE, never an eligibility test: the rank
# is the FOURTH term of the selection key, below pillar coverage and below
# category coverage within a pillar, so it decides which question represents a
# (pillar, category) in a given round and never how many rounds anything gets.
# Putting it any higher would let a well-stocked industry starve a pillar, which
# is the exact failure `engine._round_robin_key_for` exists to prevent.

#: `question_industry_mapping.applicability_type = 'primary'` -- a defining
#: question for this industry.
PRIMARY_RANK = 0
#: `applicability_type = 'supporting'` -- relevant but not core.
SUPPORTING_RANK = 1
#: A UNIVERSAL question whose problem this industry weights heavily. Ranks below
#: the industry's own questions because a question written for the industry is a
#: stronger statement of relevance than a weight applied to a general one.
STRONG_WEIGHT_RANK = 2
#: A universal question whose problem this industry weights mildly.
WEAK_WEIGHT_RANK = 3
#: Everything else. The default, and the rank the whole catalogue falls to when
#: no industry is known or no industry data can be read -- which reproduces the
#: pre-industry order exactly.
UNIVERSAL_RANK = 4

#: Where `industries.top_pain_point_weights` stops being a nudge and starts
#: being a statement. The seeded values are exactly 1.05, 1.15, 1.3 and 1.5, so
#: this splits them 2-2 rather than cutting through a cluster: 1.3 and 1.5 are
#: "this is what goes wrong in this industry", 1.05 and 1.15 are "worth a little
#: more than average". Inclusive, so a weight of exactly 1.3 is strong.
STRONG_WEIGHT_THRESHOLD = Decimal("1.3")

#: The rank every question gets when there is nothing to rank on. A constant
#: means the term contributes nothing to the ordering, so the key degrades to
#: exactly what it was before industry existed.
_NO_SIGNAL: Callable[[Any], int] = lambda _question: UNIVERSAL_RANK  # noqa: E731


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


def normalise_weights(raw: Any) -> dict[str, Decimal]:
    """`industries.top_pain_point_weights` as {problem_code: weight}, or {}.

    The column is free-shaped JSONB whose format was never formalised -- see
    `reasoning/config.IndustryProbabilityStrategy`, which says so in as many
    words. Seeded rows look like {"IVA-001": 1.5, "SAL-005": 1.5}, but only four
    of the thirty industries have a value at all; the other twenty-six carry the
    `'{}'` default because the migration seeds only name, code and description.

    So this is deliberately forgiving and never raises: anything that is not a
    mapping, any key that is not a string, and any value that will not read as a
    number is skipped rather than failing the sort. A weight the shape of which
    we cannot understand is no signal, and no signal is the ordinary case here
    rather than an error.
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Decimal] = {}
    for code, value in raw.items():
        if not isinstance(code, str) or not code.strip():
            continue
        if isinstance(value, bool):                # bool is an int; not a weight
            continue
        try:
            out[code.strip().upper()] = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return out


#: Fewest questions each in-scope pillar must still be able to receive after
#: the opening block has taken its share.
#:
#: Two, not one, and not `MIN_ANSWERS_PER_PILLAR_SCORE` (3). A pillar with one
#: answer scores 0, 50 or 100 and nothing between, which is why the scoring
#: floor exists at all; two is the fewest that can produce anything else. Three
#: would be the honest scoring floor, but this is a guard on a preference, not
#: the scoring rule -- it exists to stop the opening block starving coverage,
#: and pitching it at the scoring floor would shrink the block at exactly the
#: stages (Ideation, Validation) where the industry signal is most of what
#: distinguishes two founders with nothing built.
MIN_QUESTIONS_PER_PILLAR = 2


def requested_opening(stage_order: Any, budget: int, per_stage, share: float) -> int:
    """The opening block size ASKED FOR, before any bound is applied.

    The per-stage table wins wherever it has an entry -- it is the product
    judgement, and it is not a fraction of anything. The share is the fallback
    for a stage the table does not name and for a founder whose stage cannot be
    read at all, which is the same situation the rest of this module treats as
    unknown rather than as zero.

    Never raises: an unusable stage_order or a table holding something other
    than an int falls through to the share.
    """
    try:
        if per_stage:
            requested = per_stage.get(int(stage_order))
            if requested is not None:
                return max(0, int(requested))
    except (TypeError, ValueError):                        # noqa: BLE001
        pass
    if share <= 0:
        return 0
    return int(budget * min(share, 1.0))


def opening_block_size(
    budget: int,
    pillars_in_scope: int,
    requested: int,
    available: int,
) -> int:
    """How many of the first questions are reserved for the founder's industry.

    Three independent limits, smallest wins:

      * `requested` -- the product decision, per stage (see
        `Settings.INDUSTRY_OPENING_QUESTIONS`).
      * what is left after every in-scope pillar is guaranteed
        MIN_QUESTIONS_PER_PILLAR. This is the guard that matters: the industry
        banks cover two to four pillars out of six (see
        `Settings.INDUSTRY_OPENING_SHARE` for the measurements), so an
        unguarded block would leave the pillars it does not touch with nothing.
        The shipped per-stage numbers sit exactly on this bound at Ideation and
        Validation and comfortably inside it everywhere else, so it binds only
        if someone raises them.
      * `available` -- how many industry questions this founder's stage
        actually has. Reserving fourteen slots when the bank holds four would
        idle ten, and the block is a head start, not a quota.

    Returns 0 rather than raising for any nonsensical input -- a negative
    budget, a request larger than the budget, no pillars in scope. 0 means "no
    opening block", which is the pre-existing behaviour and always safe.
    """
    if budget <= 0 or available <= 0 or requested <= 0:
        return 0
    reserved_for_coverage = max(0, pillars_in_scope) * MIN_QUESTIONS_PER_PILLAR
    by_coverage = budget - reserved_for_coverage
    return max(0, min(requested, by_coverage, available))


def relevance_ranker(
    applicability: dict[int, str] | None,
    problem_to_code: dict[int, str] | None,
    weights: dict[str, Decimal] | None,
) -> Callable[[Any], int]:
    """A `question -> rank` function, lower being more relevant to this founder.

    Two independent signals, checked strongest first:

      1. `question_industry_mapping` -- this question was WRITTEN for the
         founder's industry. After `excluded_question_ids` has run, the only
         mapped questions left in the candidate set are the founder's own, so
         this is a straight primary/supporting read.
      2. `industries.top_pain_point_weights` -- this question's problem is one
         the founder's industry says goes wrong more often than average. Applies
         to UNIVERSAL questions, which is the point: it is how a SaaS founder
         gets the general churn and pricing questions ahead of the general
         supply-chain ones without either being industry-owned.

    Returns a constant when neither signal is available, so the term vanishes
    from the sort rather than reordering anything on no evidence. That is the
    ordinary state for twenty-six of the thirty industries today.
    """
    applicability = applicability or {}
    problem_to_code = problem_to_code or {}
    weights = weights or {}
    if not applicability and not weights:
        return _NO_SIGNAL

    def rank(question: Any) -> int:
        kind = applicability.get(getattr(question, "question_id", None))
        if kind == "primary":
            return PRIMARY_RANK
        if kind == "supporting":
            return SUPPORTING_RANK
        # `.get() or ""`: a problem with no code recorded is UNKNOWN, so it
        # carries no weight and falls to universal -- never an error, and never
        # a reason to reorder. Same reading as the dimension and context maps.
        code = (problem_to_code.get(getattr(question, "problem_id", None)) or "").upper()
        weight = weights.get(code)
        if weight is None:
            return UNIVERSAL_RANK
        return STRONG_WEIGHT_RANK if weight >= STRONG_WEIGHT_THRESHOLD else WEAK_WEIGHT_RANK

    return rank
