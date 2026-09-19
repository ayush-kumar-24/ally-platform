"""Where the founder wants to go, and what that destination requires.

THE ONE THING THIS MODULE DOES:

    TargetStateContext  x  capability_requirements   ->   RequiredCapability[]

and the one thing it must never do is look at an answer. There is no evidence
here, no comparison, no MISSING and no gap. A requirement is a statement about
the DESTINATION; whether the founder has it is Step 7, and the comparison is
Step 8. Keeping those apart in separate modules is what makes "no evidence, no
claim of a gap" a structural property instead of a promise.

TARGET REVENUE IS NOT A DIAGNOSIS. The band and horizon are lookup keys. No
subtraction between current and target revenue happens anywhere in this module,
and there is nothing to store such a number in. A founder who states a 10x
target and answers no questions gets a list of requirements and zero findings.

SEPARATE FROM FounderContext, ON PURPOSE. `FounderContext` answers "what is
true about this founder" and its tokens GATE questions -- a value in it can
remove something from the diagnosis. A target is an aspiration: it must never
be able to remove a question, and it must never be mistaken for evidence. Two
value objects keep that impossible rather than merely discouraged. They are
composed at the call site (`resolve_requirements` takes both) rather than
nested, so neither owns the other.

THE CASCADE. Requirement rows carry a context predicate whose every dimension is
nullable, and NULL means wildcard:

    industry_code  business_model  from_stage_order  target_revenue_band
    target_time_horizon

A row APPLIES when every non-NULL dimension matches the founder. Among applying
rows for one capability, the winner is:

    1. highest specificity   -- the number of non-NULL dimensions
    2. then highest from_stage_order  -- the tightest lower bound
    3. still tied, and the requirements differ -> AmbiguousRequirementError

Rule 3 is deliberately an exception rather than a pick. Two equally specific
rules that disagree are a curation error, and silently choosing one would make
a founder's requirements depend on insertion order. (The database also refuses
two rows with the SAME predicate -- see the unique index with NULLS NOT
DISTINCT -- so this fires only for genuinely different predicates of equal
weight.)

UNKNOWN NARROWS NOTHING. A founder whose industry is unknown matches every row
whose industry is NULL, exactly as they would if their industry were known and
different. What unknown context costs them is the SPECIFIC rows, never the
wildcard ones -- so an incomplete profile yields a more generic requirement set,
never an empty one. This is Step 4's UNKNOWN-is-not-NO rule, applied to the
knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.core.logger import logger

#: The two values `necessity` may take. `core` means the destination is not
#: reachable without it; `contextual` means it matters for this context but a
#: business could get there without it. Nothing in Step 6 acts on the
#: difference -- it is carried so Step 8 can prioritise gaps without inventing a
#: severity of its own.
NECESSITY_CORE = "core"
NECESSITY_CONTEXTUAL = "contextual"
NECESSITY_VALUES = frozenset({NECESSITY_CORE, NECESSITY_CONTEXTUAL})

#: The context dimensions a requirement row may constrain, in a fixed order.
#: Specificity is the count of these that are non-NULL, so the order matters
#: only for logging -- but it is fixed so two readers see the same thing.
CONTEXT_DIMENSIONS = (
    "industry_code",
    "business_model",
    "from_stage_order",
    "target_revenue_band",
    "target_time_horizon",
)


class AmbiguousRequirementError(Exception):
    """Two equally specific rules disagree about one capability.

    Raised rather than resolved. Picking one would make a founder's requirements
    depend on which row was inserted first, and the curator would never find
    out. The message names the capability and both rows so the fix is obvious.
    """


@dataclass(frozen=True)
class TargetStateContext:
    """Where the founder says they want the business to be.

    Every field is optional and None means "not stated". None is never an
    assumption: a founder who has not given a target is not a founder targeting
    nothing, and `is_stated` is what callers check before doing anything at all.
    """

    target_revenue_band: str | None = None
    target_time_horizon: str | None = None

    @classmethod
    def from_founder(cls, founder: Any) -> "TargetStateContext":
        """Read the target off a founder row. Pure, never raises."""
        return cls(
            target_revenue_band=_clean(getattr(founder, "target_revenue_band", None)),
            target_time_horizon=_clean(getattr(founder, "target_time_horizon", None)),
        )

    @property
    def is_stated(self) -> bool:
        """Whether the founder has said anything about a destination.

        A target with neither band nor horizon selects only rows that constrain
        neither -- which, in a knowledge base organised by destination, is
        almost nothing. Callers check this rather than inferring it from an
        empty result, because "they did not tell us" and "we know of no
        requirements" are different facts.
        """
        return bool(self.target_revenue_band or self.target_time_horizon)

    def describe(self) -> dict[str, Any]:
        """Log-safe. Carries no free text the founder typed."""
        return {
            "target_revenue_band": self.target_revenue_band,
            "target_time_horizon": self.target_time_horizon,
            "target_stated": self.is_stated,
        }


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


@dataclass(frozen=True)
class RequiredCapability:
    """One capability the destination needs, and why.

    Deliberately says nothing about whether the founder HAS it. There is no
    field here for an observed level and no field for a gap, because this object
    is produced before any evidence is consulted.
    """

    capability_id: int
    capability_code: str
    required_level: CapabilityLevel
    necessity: str
    rationale: str
    #: The row that won, and how specific it was -- so "why am I being told I
    #: need this" is answerable without re-running the resolution.
    requirement_id: int
    specificity: int
    #: The dimensions the winning row actually constrained.
    matched_on: tuple[str, ...]

    @property
    def is_core(self) -> bool:
        return self.necessity == NECESSITY_CORE


def _row_get(row: Any, name: str) -> Any:
    """Read a field off a row that may be an ORM object, a mapping or a double."""
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _applies(row: Any, founder_context: Any, target: TargetStateContext) -> bool:
    """Does this row's predicate hold for this founder?

    A NULL dimension always holds. A non-NULL dimension holds only when the
    founder's corresponding value is KNOWN and matches -- unknown context can
    never satisfy a specific rule, which is what stops a blank profile
    collecting requirements nobody established.
    """
    industry = _row_get(row, "industry_code")
    if industry is not None:
        if not getattr(founder_context, "industry_code", None):
            return False
        if founder_context.industry_code.lower() != str(industry).lower():
            return False

    model = _row_get(row, "business_model")
    if model is not None:
        founder_model = getattr(founder_context, "business_model", None)
        if not founder_model or founder_model.lower() != str(model).lower():
            return False

    from_stage = _row_get(row, "from_stage_order")
    if from_stage is not None:
        stage_order = getattr(founder_context, "stage_order", None)
        # Lower bound, inclusive. An unknown stage cannot satisfy it.
        if not isinstance(stage_order, int) or stage_order < int(from_stage):
            return False

    band = _row_get(row, "target_revenue_band")
    if band is not None and target.target_revenue_band != band:
        return False

    horizon = _row_get(row, "target_time_horizon")
    if horizon is not None and target.target_time_horizon != horizon:
        return False

    return True


def _specificity(row: Any) -> tuple[int, tuple[str, ...]]:
    """How many dimensions this row constrains, and which."""
    matched = tuple(d for d in CONTEXT_DIMENSIONS if _row_get(row, d) is not None)
    return len(matched), matched


def resolve_requirements(
    rows: Sequence[Any],
    founder_context: Any,
    target: TargetStateContext,
) -> tuple[RequiredCapability, ...]:
    """The Required Capability Model for one founder. Pure; no database.

    `rows` is every `capability_requirements` row (the table is small reference
    data -- 54 rows today -- so filtering in Python keeps the cascade in one
    readable place rather than half in SQL).

    Returns at most one RequiredCapability per capability, ordered by capability
    code so the result is stable across calls and across processes.

    Raises AmbiguousRequirementError when two equally specific rules disagree.
    """
    by_capability: dict[int, list[Any]] = {}
    for row in rows:
        if not _applies(row, founder_context, target):
            continue
        by_capability.setdefault(_row_get(row, "capability_id"), []).append(row)

    resolved: list[RequiredCapability] = []
    for capability_id, candidates in by_capability.items():
        winner = _pick(capability_id, candidates)
        specificity, matched = _specificity(winner)
        resolved.append(RequiredCapability(
            capability_id=capability_id,
            capability_code=_row_get(winner, "capability_code"),
            required_level=CapabilityLevel(int(_row_get(winner, "required_level"))),
            necessity=_row_get(winner, "necessity"),
            rationale=_row_get(winner, "rationale"),
            requirement_id=_row_get(winner, "requirement_id"),
            specificity=specificity,
            matched_on=matched,
        ))

    resolved.sort(key=lambda r: r.capability_code)
    if resolved:
        logger.info(
            "target-state requirements resolved",
            extra={
                "stage": "target_state",
                **target.describe(),
                "capabilities_required": len(resolved),
                "core": sum(1 for r in resolved if r.is_core),
            },
        )
    return tuple(resolved)


def _pick(capability_id: int, candidates: list[Any]) -> Any:
    """The winning row for one capability, or an error if that is not decidable."""
    best_specificity = max(_specificity(r)[0] for r in candidates)
    finalists = [r for r in candidates if _specificity(r)[0] == best_specificity]
    if len(finalists) == 1:
        return finalists[0]

    # Tie-break: the tightest stage lower bound. A row that says "from stage 4"
    # is a narrower claim than one that says "from stage 2", so it wins -- and
    # this is the only tie-break, because any other would be a preference
    # dressed up as a rule.
    best_stage = max((_row_get(r, "from_stage_order") or 0) for r in finalists)
    finalists = [r for r in finalists
                 if (_row_get(r, "from_stage_order") or 0) == best_stage]
    if len(finalists) == 1:
        return finalists[0]

    # Identical requirements from different predicates are harmless -- both say
    # the same thing, so say it. Only a genuine disagreement is an error.
    distinct = {(int(_row_get(r, "required_level")), _row_get(r, "necessity"))
                for r in finalists}
    if len(distinct) == 1:
        return min(finalists, key=lambda r: _row_get(r, "requirement_id"))

    raise AmbiguousRequirementError(
        f"capability_id {capability_id} has {len(finalists)} equally specific "
        f"requirement rows that disagree: "
        + "; ".join(
            f"requirement {_row_get(r, 'requirement_id')} -> "
            f"level {_row_get(r, 'required_level')} {_row_get(r, 'necessity')}"
            for r in sorted(finalists, key=lambda r: _row_get(r, "requirement_id"))
        )
        + ". Two rules of equal weight cannot both be right; fix the curation."
    )
