"""CAPABILITY EVIDENCE -> CURRENT CAPABILITY ASSESSMENT. A read model, not a table.

WHAT THIS MODULE ANSWERS, EXACTLY: "given the observations recorded so far for
one capability, what level does Ally currently have evidence for?" It does not
ask what level a founder SHOULD have (that is `target_state.py`, untouched
here), and it does not compare the two (the Gap Engine, Step 8+, does not exist
yet -- see capability_taxonomy tests for the boundary this keeps).

NO NEW TABLE, on purpose, and this mirrors a decision already made once in this
codebase. `target_state.resolve_requirements` computes the Required Capability
Model as a PURE FUNCTION over `capability_requirements` rows -- it is never
materialised, because the underlying rows are already persisted, already small,
and recomputing from them is cheap and always current. The same reasoning
applies here with more force: `capability_evidence` rows are already persisted
(Step 7B), already immutable (nothing here or elsewhere ever updates or deletes
one), and a capability accumulates single digits of observations per session,
not thousands. A stored "assessment" table would need invalidation logic every
time a new observation lands -- exactly the incremental-recomputation-safety
problem the step brief warns against solving prematurely. Not storing anything
here makes that problem not exist rather than solving it cleverly.

THE AGGREGATION PROBLEM IS NARROWER THAN IT LOOKS. Each of a capability's four
evidence criteria could, taken alone, seem to need its own rule for how it
combines into an overall level -- but that inference already happened, once,
per observation, in Step 7B: `capability_evidence.observed_level` is the
extractor's full 0-3 judgment for that ONE answer, grounded in whichever
criterion it cited (or none). The criteria carry no stored level of their own
(`capability_evidence_criteria` has no level column, by Step 5 design) and nothing
here reads them. So this module's job is not "infer a level from four criteria"
-- it is "combine several ALREADY-LEVELLED observations into one current
reading", which is a well-posed, narrow problem with no ambiguity to report.

THE RULE: LOWEST CONFIDENT READING, deterministic and explainable.

    1. An observation PARTICIPATES only if confidence >= MIN_CONFIDENCE
       (capability_evidence.MIN_CONFIDENCE -- the SAME 0.6 floor the Step 7B
       extractor already enforces at write time, reused rather than a second
       number invented here; see that module's own comment on why it is
       public).
    2. current_level = min(observed_level for every participating observation).
    3. Zero participating observations -> UNASSESSED. Not level 0, not level 1,
       not a default of any kind -- the absence of a row (or the absence of a
       row that clears the floor) is the absence of a claim.

MIN, NOT AVERAGE, NOT MAJORITY, NOT MOST-RECENT. Maturity is not a statistic:
"you have a documented process" (level 2) and "you personally do it" (level 1)
about the SAME capability are not two data points to blend -- the second
directly contradicts the first, and the conservative reading is the one that
does not credit a founder with more independence than the weakest confirmed
observation shows. This is also what makes "more evidence never means a higher
level" true by construction: ten Level-1 observations MIN to Level 1, exactly
as one does; one strong Level-3 observation MINs to Level 3 on its own,
exactly as the step brief's own example requires.

A WEAK OBSERVATION CANNOT DOWNGRADE STRONG EVIDENCE, and the confidence floor
is the entire mechanism -- not a second rule layered on top of MIN. An
observation below the floor never enters the MIN at all, so it cannot pull the
result down regardless of its level. There is deliberately no separate
"outlier rejection" step: the floor already IS the participation test, and
adding a second one would be an unjustified extra rule the brief explicitly
warns against ("do not invent a complex statistical model").

DETERMINISM. `min()` over a set of integers has one answer regardless of
insertion order; ties among evidence at the winning level are resolved by
lowest `evidence_id` for a stable `supporting_evidence_ids` order, not by
recency or magnitude. No LLM participates in this module at all -- it is pure
Python over already-persisted, already-judged rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.api.v1.diagnosis.capability_evidence import MIN_CONFIDENCE
from app.api.v1.diagnosis.capability_levels import UNASSESSED, CapabilityLevel


def _get(row: Any, name: str) -> Any:
    """Read a field off a row that may be a dict, a RowMapping, or a double."""
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


@dataclass(frozen=True)
class CapabilityAssessment:
    """The current read for ONE capability, derived from its observations.

    `current_level` is `None` exactly when `status` is UNASSESSED -- the two
    never disagree, by construction (see `assess_capability`). There is no
    field here that could be mistaken for a gap or a requirement: this object
    is produced without ever looking at `capability_requirements`.
    """

    capability_id: int
    capability_code: str
    current_level: CapabilityLevel | None
    #: The evidence_id(s) whose observed_level EQUALS current_level and which
    #: cleared the confidence floor -- the rows that DETERMINE this result.
    #: "Why is this founder Level 1 for FND-DELEG" points here; from an
    #: evidence_id, `capability_evidence_for_session` (or a direct lookup)
    #: reaches answer_id -> question_id, completing the chain the step brief
    #: asks for without a second aggregation.
    supporting_evidence_ids: tuple[int, ...]
    #: Every observation that cleared the floor, at any level -- what the
    #: assessment considered. A superset of `supporting_evidence_ids` whenever
    #: more than one level was confidently observed (e.g. a 2 and a 1 both
    #: participated; only the 1 supports the result, but the 2 was not
    #: nothing -- it is visible here, not silently discarded).
    considered_evidence_ids: tuple[int, ...]
    #: Observations that existed but did not clear the floor. Kept so "was
    #: there contradicting evidence that got overridden, or was there none at
    #: all" is answerable without a second query -- a different question from
    #: "what is the level", and one a debugging session will actually ask.
    excluded_evidence_ids: tuple[int, ...]

    @property
    def status(self) -> str:
        return UNASSESSED if self.current_level is None else "assessed"

    @property
    def is_assessed(self) -> bool:
        return self.current_level is not None


def assess_capability(
    capability_id: int, capability_code: str, evidence_rows: Iterable[Any],
) -> CapabilityAssessment:
    """The lowest-confident-reading rule, over one capability's observations.

    Pure: no database, no LLM, no side effect. `evidence_rows` is every
    observation for THIS capability already (the caller partitions by
    capability_id -- see `assess_capabilities`); this function does not filter
    by capability itself, so it cannot silently mix two capabilities' rows.
    """
    participating: list[tuple[int, int]] = []   # (evidence_id, observed_level)
    excluded: list[int] = []

    for row in evidence_rows:
        evidence_id = _get(row, "evidence_id")
        level = _get(row, "observed_level")
        confidence = _get(row, "confidence")
        if confidence is None or float(confidence) < MIN_CONFIDENCE:
            excluded.append(evidence_id)
            continue
        participating.append((evidence_id, int(level)))

    if not participating:
        return CapabilityAssessment(
            capability_id=capability_id,
            capability_code=capability_code,
            current_level=None,
            supporting_evidence_ids=(),
            considered_evidence_ids=(),
            excluded_evidence_ids=tuple(sorted(excluded)),
        )

    current = min(level for _eid, level in participating)
    supporting = tuple(sorted(eid for eid, level in participating if level == current))
    considered = tuple(sorted(eid for eid, _level in participating))

    return CapabilityAssessment(
        capability_id=capability_id,
        capability_code=capability_code,
        current_level=CapabilityLevel(current),
        supporting_evidence_ids=supporting,
        considered_evidence_ids=considered,
        excluded_evidence_ids=tuple(sorted(excluded)),
    )


def assess_capabilities(evidence_rows: Iterable[Any]) -> tuple[CapabilityAssessment, ...]:
    """One assessment per capability that has AT LEAST ONE observation (of any
    confidence -- a capability with only excluded observations still gets an
    UNASSESSED row, distinct from a capability with none at all, so a caller
    can tell "we asked but got nothing usable" from "we never asked").

    Ordered by capability_code, so the result is stable across calls -- the
    same discipline `target_state.resolve_requirements` already applies to its
    own output, for the same reason: two callers must never see the two
    capabilities in a different order for the identical input.
    """
    by_capability: dict[int, list[Any]] = {}
    codes: dict[int, str] = {}
    for row in evidence_rows:
        capability_id = _get(row, "capability_id")
        by_capability.setdefault(capability_id, []).append(row)
        codes.setdefault(capability_id, _get(row, "capability_code"))

    results = [
        assess_capability(capability_id, codes[capability_id], rows)
        for capability_id, rows in by_capability.items()
    ]
    results.sort(key=lambda a: a.capability_code)
    return tuple(results)
