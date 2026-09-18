"""The canonical, immutable view of who a founder is, for every layer that gates.

WHY THIS EXISTS. Context was collected by onboarding, persisted on `founders`,
and then read ad hoc: `founder_brief.py` rendered it into a prompt,
`context_scope.context_tokens` derived one token from it, and the selection
engine read `founder.stage` and nothing else. Three readers, three shapes, and
the only one that could REMOVE a question knew about fundraising alone.

This module is the single derivation. Question eligibility, the advisor prompt,
the reasoning context and recommendation matching all read the same object, so
"what does Ally know about this founder" has exactly one answer.

THE THREE-VALUED CORE. Every precondition resolves to SATISFIED, CONTRADICTED
or UNKNOWN, and the middle one is why this is a value object rather than a dict:

    SATISFIED     the founder's data says yes      -> question stays eligible
    CONTRADICTED  the founder's data says no       -> question is removed
    UNKNOWN       we have no data for that family  -> question stays eligible,
                                                      marked applicability_uncertain

UNKNOWN MUST NEVER MEAN NO. A founder who never told us their team size is not
a solo founder; they are a founder we did not ask. Removing team questions from
them would silently under-diagnose exactly the people whose onboarding was
incomplete. Only a positive statement contradicts.

That asymmetry is already the rule the fundraising gate follows -- see
`context_scope.context_tokens` -- and this generalises it to every family.

FAMILIES, NOT FLAT TOKENS. `verdict()` resolves an unrecognised token within a
KNOWN family to CONTRADICTED, which is what makes industry gating work without
enumerating every industry: a founder known to be `agritech` contradicts
`industry:fintech` because the industry family is known and fintech is not it.
The same founder with `industry_mapped_id IS NULL` returns UNKNOWN for both.

PURE AND CHEAP. `from_founder` does no database work of its own and never
raises: it reads attributes off whatever it is handed, so a unit test builds one
from a SimpleNamespace. It is constructed once per request, not once per
question. (`industry_code` is the one value that lives on another table; pass it
explicitly, or let the already-loaded `founder.industry_mapped` relationship
supply it.)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

# --- token families ---------------------------------------------------------
#
# A family is a question Ally can answer about a founder ("what industry are
# they in?"). A token is one possible answer ("industry:agritech"). Preconditions
# are written as tokens; `verdict` resolves them through the family, so a known
# family with a different answer is a CONTRADICTION rather than an UNKNOWN.

FAMILY_STAGE = "stage"
FAMILY_INDUSTRY = "industry"
FAMILY_TEAM = "team"
FAMILY_BUSINESS_MODEL = "business_model"
FAMILY_REVENUE = "revenue"
FAMILY_CHALLENGES = "challenges"
#: Fundraising intent is its OWN family, separate from the challenges it is
#: derived from, because the two have different negative semantics. Answering
#: the challenges question at all settles fundraising ("they were shown the
#: option and did not pick it" -- the rule `context_scope.context_tokens` has
#: shipped since the gate existed). It does NOT settle the others: the question
#: is "pick up to three", so a founder with a marketing problem who picked
#: three other things has not denied marketing. Collapsing the two families
#: would either break the live fundraising gate or over-gate everything else.
FAMILY_FUNDRAISING = "fundraising"

ALL_FAMILIES = frozenset({
    FAMILY_STAGE, FAMILY_INDUSTRY, FAMILY_TEAM,
    FAMILY_BUSINESS_MODEL, FAMILY_REVENUE, FAMILY_CHALLENGES, FAMILY_FUNDRAISING,
})

#: Tokens that carry no `prefix:` because they read as English in a precondition
#: column -- `has_team` is what a curator writes against the `hiring` tag.
TOKEN_HAS_TEAM = "has_team"
TOKEN_HAS_REVENUE = "has_revenue"
#: Kept identical to `context_scope.FUNDRAISING_INTENT`; that module now derives
#: it from here rather than from the founder row directly.
TOKEN_FUNDRAISING_INTENT = "fundraising_intent"

_BARE_TOKEN_FAMILIES = {
    TOKEN_HAS_TEAM: FAMILY_TEAM,
    TOKEN_HAS_REVENUE: FAMILY_REVENUE,
    TOKEN_FUNDRAISING_INTENT: FAMILY_FUNDRAISING,
}

_PREFIX_FAMILIES = {
    "stage": FAMILY_STAGE,
    "industry": FAMILY_INDUSTRY,
    "team": FAMILY_TEAM,
    "model": FAMILY_BUSINESS_MODEL,
    "challenge": FAMILY_CHALLENGES,
}

#: The onboarding option that states fundraising intent. Sourced from
#: `frontend/src/data/onboardingQuestions.js`; `current_challenges` has no CHECK
#: constraint, so this label is the only contract. Compared as a whole stripped
#: label, case-insensitively, never as a substring: "Fundraising timeline" is a
#: different answer and matching it would make the gate depend on free text.
FUNDRAISING_CHALLENGE = "Fundraising"

#: `current_revenue` values that mean "no revenue yet". Everything else in the
#: CurrentRevenue literal is a band with money in it.
_PRE_REVENUE_VALUES = frozenset({"pre_revenue", "0", "none", "nil"})

#: `team_size` values, from the `founders_team_size_check` constraint. Only
#: `solo` denies `has_team`; every other bucket asserts it.
_SOLO_TEAM_SIZE = "solo"


class Applicability(str, Enum):
    """The three-valued answer to "does this precondition hold for this founder?"."""

    SATISFIED = "satisfied"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


def family_of(token: str) -> str | None:
    """The family a precondition token belongs to, or None when unrecognised.

    An unrecognised token is deliberately not an error here. Preconditions are
    DATA (`question_tags.precondition_token`), so a typo or a token from a newer
    release must degrade to "cannot evaluate" -- which `verdict` reports as
    UNKNOWN, keeping the question eligible. Validation catches the typo; the
    interview does not stop for it.
    """
    if not token:
        return None
    if token in _BARE_TOKEN_FAMILIES:
        return _BARE_TOKEN_FAMILIES[token]
    prefix, _, rest = token.partition(":")
    if rest:
        return _PREFIX_FAMILIES.get(prefix)
    return None


def _clean_str(value: Any) -> str | None:
    """A non-empty stripped string, or None. Never raises on an odd type."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _stated_challenges(founder: Any) -> tuple[str, ...] | None:
    """The challenges the founder explicitly picked, or None when unreadable.

    None is the UNKNOWN verdict, returned for every shape that is not a
    non-empty list of non-empty strings: NULL, `[]`, a bare string, a dict, a
    list of nulls. Operationally they all mean "onboarding gave us no usable
    answer", and none is evidence about what the founder is or is not doing.
    """
    raw = getattr(founder, "current_challenges", None)
    if not isinstance(raw, list):
        return None
    picked = tuple(c for c in (_clean_str(v) for v in raw) if c)
    return picked or None


@dataclass(frozen=True)
class FounderContext:
    """Everything Ally knows about a founder that can decide what to ask.

    `tokens` / `denied` / `unknowns` are the whole contract; the named fields
    beside them exist so callers that need the raw value (a prompt line, a
    recommendation filter) do not have to parse a token back apart.
    """

    stage_order: int | None = None
    stage_name: str | None = None
    industry_code: str | None = None
    team_size: str | None = None
    business_model: str | None = None
    revenue_band: str | None = None
    challenges: tuple[str, ...] = ()

    #: Preconditions this founder SATISFIES.
    tokens: frozenset[str] = field(default_factory=frozenset)
    #: Preconditions this founder explicitly CONTRADICTS. Held separately from
    #: "absent from tokens" because a bare absence inside an unknown family is
    #: not a contradiction -- see `verdict`.
    denied: frozenset[str] = field(default_factory=frozenset)
    #: Families with no usable data. A precondition in one of these is UNKNOWN,
    #: which keeps its question eligible and marks it applicability_uncertain.
    unknowns: frozenset[str] = field(default_factory=frozenset)

    # --- construction -----------------------------------------------------
    @classmethod
    def from_founder(cls, founder: Any, *, industry_code: str | None = None) -> "FounderContext":
        """Derive the context from a founder row. Pure, cheap, never raises.

        `industry_code` is the only value not on `founders` itself. Pass it when
        the caller has already resolved `industry_mapped_id` (the service does);
        otherwise an already-loaded `founder.industry_mapped` relationship is
        read. An `industry_mapped_id` we cannot name is UNKNOWN, not a
        contradiction -- we cannot gate on an id whose code we do not have.
        """
        tokens: set[str] = set()
        denied: set[str] = set()
        unknowns: set[str] = set()

        # --- stage ---------------------------------------------------------
        stage = getattr(founder, "stage", None)
        stage_order = getattr(stage, "stage_order", None)
        stage_name = _clean_str(getattr(stage, "stage_name", None))
        if isinstance(stage_order, int) and not isinstance(stage_order, bool):
            tokens.add(f"stage:{stage_order}")
        else:
            stage_order = None
            unknowns.add(FAMILY_STAGE)

        # --- industry ------------------------------------------------------
        code = _clean_str(industry_code)
        if code is None:
            mapped = getattr(founder, "industry_mapped", None)
            code = _clean_str(getattr(mapped, "industry_code", None))
        if code:
            tokens.add(f"industry:{code.lower()}")
        else:
            unknowns.add(FAMILY_INDUSTRY)

        # --- team ----------------------------------------------------------
        # The one family where a value both asserts and denies: "solo" is a
        # positive statement that there is no team, which is what makes a team
        # question CONTRADICTED rather than merely unsatisfied.
        team_size = _clean_str(getattr(founder, "team_size", None))
        if team_size:
            tokens.add(f"team:{team_size}")
            if team_size == _SOLO_TEAM_SIZE:
                denied.add(TOKEN_HAS_TEAM)
            else:
                tokens.add(TOKEN_HAS_TEAM)
        else:
            unknowns.add(FAMILY_TEAM)

        # --- business model -------------------------------------------------
        business_model = _clean_str(getattr(founder, "business_model", None))
        if business_model:
            tokens.add(f"model:{business_model.lower()}")
        else:
            unknowns.add(FAMILY_BUSINESS_MODEL)

        # --- revenue --------------------------------------------------------
        revenue_band = _clean_str(getattr(founder, "current_revenue", None))
        if revenue_band:
            if revenue_band.lower() in _PRE_REVENUE_VALUES:
                denied.add(TOKEN_HAS_REVENUE)
            else:
                tokens.add(TOKEN_HAS_REVENUE)
        else:
            unknowns.add(FAMILY_REVENUE)

        # --- challenges / fundraising intent --------------------------------
        # Asymmetric on purpose, and this is the asymmetry the fundraising gate
        # has always used: ticking "Fundraising" is an unambiguous statement, so
        # the positive case is trustworthy. NOT ticking it is weak evidence --
        # the question is "biggest challenge, pick up to three", so a founder
        # mid-raise who is more worried about sales will not tick it. Nothing in
        # the schema means "bootstrapped", so absence is UNKNOWN, never denial.
        challenges = _stated_challenges(founder)
        if challenges is None:
            challenges = ()
            unknowns.add(FAMILY_CHALLENGES)
            unknowns.add(FAMILY_FUNDRAISING)
        else:
            for challenge in challenges:
                tokens.add(f"challenge:{challenge.lower()}")
            # Fundraising is settled either way once the question was answered;
            # the other challenges are not (see FAMILY_FUNDRAISING above).
            if any(c.casefold() == FUNDRAISING_CHALLENGE.casefold() for c in challenges):
                tokens.add(TOKEN_FUNDRAISING_INTENT)
            else:
                denied.add(TOKEN_FUNDRAISING_INTENT)
            unknowns.add(FAMILY_CHALLENGES)

        return cls(
            stage_order=stage_order,
            stage_name=stage_name,
            industry_code=code.lower() if code else None,
            team_size=team_size,
            business_model=business_model,
            revenue_band=revenue_band,
            challenges=challenges,
            tokens=frozenset(tokens),
            denied=frozenset(denied),
            unknowns=frozenset(unknowns),
        )

    def with_session_facts(self, facts: Mapping[str, bool] | None) -> "FounderContext":
        """A copy carrying what THIS SESSION learned, e.g. from an N/A answer.

        A fact is a token the founder's own answers settled: `has_team -> False`
        after "I don't have a team". It resolves the family, so the remaining
        team questions become CONTRADICTED instead of UNKNOWN for the rest of
        the session.

        Deliberately NOT written back to `founders`. Session context is an
        observation made while asking; the profile is what the founder stated.
        Collapsing the two would let one ambiguous answer silently edit their
        record. `from_founder` is therefore always the base, and this is always
        a derived copy.

        A fact NEVER overrides a profile value: a founder who stated
        `team_size='2_5'` keeps `has_team` satisfied even if one answer looked
        otherwise. Profile beats inference; the disagreement is a data-quality
        signal for logging, not a silent correction.
        """
        if not facts:
            return self

        tokens = set(self.tokens)
        denied = set(self.denied)
        unknowns = set(self.unknowns)
        changed = False

        for token, value in facts.items():
            token = _clean_str(token)
            if token is None:
                continue
            family = family_of(token)
            if family is None:
                continue
            # Profile wins. Only an UNKNOWN family can be settled this way.
            if token in tokens or token in denied:
                continue
            if value:
                tokens.add(token)
            else:
                denied.add(token)
            unknowns.discard(family)
            changed = True

        if not changed:
            return self
        return replace(
            self,
            tokens=frozenset(tokens),
            denied=frozenset(denied),
            unknowns=frozenset(unknowns),
        )

    # --- the contract -----------------------------------------------------
    def verdict(self, token: str | None) -> Applicability:
        """Does this precondition hold? SATISFIED / CONTRADICTED / UNKNOWN.

        No precondition at all is SATISFIED -- a question with no precondition is
        universal, which is the default for all but a curated few.

        Resolution order matters:

          1. explicitly denied         -> CONTRADICTED
          2. explicitly satisfied      -> SATISFIED
          3. family unknown            -> UNKNOWN   (keep, mark uncertain)
          4. family known, token not   -> CONTRADICTED

        Rule 4 is what makes industry work without enumerating industries: a
        founder known to be agritech contradicts `industry:fintech` because the
        family is answered and fintech is not the answer. Rule 3 is what stops
        that logic firing on a founder we simply never asked.

        An unrecognised token (no family) is UNKNOWN, never CONTRADICTED: a
        curation typo must not silently delete questions.
        """
        if not token:
            return Applicability.SATISFIED
        if token in self.denied:
            return Applicability.CONTRADICTED
        if token in self.tokens:
            return Applicability.SATISFIED
        family = family_of(token)
        if family is None or family in self.unknowns:
            return Applicability.UNKNOWN
        return Applicability.CONTRADICTED

    def is_unknown_family(self, token: str | None) -> bool:
        """True when this token cannot be judged because its family has no data.

        The signal the gate turns into `applicability_uncertain`, and the advisor
        into "Not yet known: team size".
        """
        if not token:
            return False
        family = family_of(token)
        return family is None or family in self.unknowns

    @property
    def knows_industry(self) -> bool:
        """Whether industry eligibility can be evaluated at all for this founder.

        False for every founder onboarded before `industry_mapped_id` had a
        writer, which is why industry gating must fail open rather than empty
        the bank.
        """
        return FAMILY_INDUSTRY not in self.unknowns

    def describe(self) -> dict[str, Any]:
        """A small, log-safe summary. Carries no free text the founder typed."""
        return {
            "stage_order": self.stage_order,
            "industry": self.industry_code,
            "team_size": self.team_size,
            "business_model": self.business_model,
            "revenue_band": self.revenue_band,
            "fundraising_intent": TOKEN_FUNDRAISING_INTENT in self.tokens,
            "unknown_families": sorted(self.unknowns),
        }
