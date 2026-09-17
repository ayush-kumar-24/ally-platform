"""What a founder's SITUATION makes it sensible to ask about.

A THIRD AXIS, deliberately separate from the two in `stage_scope`. Stage scope
answers "is this founder far enough along to have an answer?"; this answers "is
this subject part of their situation at all?". A Series-A-ready founder who is
not raising is not too early for fundraising questions -- fundraising is simply
not something they are doing.

WHY THIS IS NOT IN `business_dna`. That module transcribes the GoXL Business DNA
document, and the document says nothing about preconditions. These are a product
rule of our own, and filing them next to a transcription would make them look
like they came from the source. They are also not taxonomy: `problems`,
`root_causes` and the categories are untouched by this module, which only reads
problem CODES and never writes or reinterprets them.

WHAT WENT WRONG WITHOUT IT. Measured on the live bank: from stage_order 2 upward
`withheld_categories` is empty, so all 101 Fundraising questions are eligible for
every founder. Worse, the pillar round-robin PROMOTES them -- the seven FND
problems carry `pillar_id = 6` (Strategic Clarity), where Fundraising is one of
only four categories at Stage 0->1, so the coverage mechanism guarantees it a
turn. `CATEGORY_SEQUENCE` puts Fundraising last "because it is the most
situational", but that key is the round-robin's third term and never decides.
A B2B SaaS founder who never mentioned investors was asked about investor
materials, and the diagnosis recommended a deck.

THE GRAIN IS THE PROBLEM, NOT THE CATEGORY. Gating `category = 'Fundraising'`
would take FND-005 "Weak Pitch and Story" with it, and that battery is about
explaining your business to a capable outsider -- Q281 asks what you would say
to "someone smart but unfamiliar with it", no investor anywhere in it. Six of
the seven FND problems presuppose a raise; one does not. Two independent counts
agree on the split: FND-005 holds 14 questions, and a separate semantic read of
the category found ~13 universal ones.
"""

from __future__ import annotations

from typing import Any

from app.core.logger import logger

#: The founder is raising, preparing to raise, or dealing with investors.
FUNDRAISING_INTENT = "fundraising_intent"

#: `problems.problem_code` -> the context token a founder must have for that
#: problem's questions to be worth asking.
#:
#: Curated and small on purpose. A problem absent from this map is
#: unconditional, which is the default and the safe direction: forgetting to add
#: an entry costs an off-topic question, while a wrong entry silently withholds
#: a whole family of problems from everyone.
#:
#: FND-005 IS DELIBERATELY ABSENT and must stay absent. "Weak Pitch and Story"
#: is about the account a founder gives of their business, which every founder
#: gives whether or not they ever meet an investor. Its Stage 0->1 battery
#: (Q281-Q286) was explicitly written for "someone smart but unfamiliar",
#: not for a deck review; the Stage 1->10+ questions under the same problem are
#: investor-framed, but they are held back by stage, not by this map. Adding
#: FND-005 here would reintroduce exactly the category-level gate this design
#: exists to avoid.
PROBLEM_PRECONDITIONS: dict[str, str] = {
    "FND-001": FUNDRAISING_INTENT,  # Raising Too Little Capital
    "FND-002": FUNDRAISING_INTENT,  # Raising Too Much Capital Too Early
    "FND-003": FUNDRAISING_INTENT,  # Wrong Investor Fit
    "FND-004": FUNDRAISING_INTENT,  # Poor Investor Management
    # FND-005 Weak Pitch and Story -- unconditional; see above.
    "FND-006": FUNDRAISING_INTENT,  # Poor Fundraising Timing
    "FND-007": FUNDRAISING_INTENT,  # Burning Cash During a Fundraise
}

#: The onboarding option that states fundraising intent.
#:
#: One named constant because the label has NO database backing: there is no
#: CHECK constraint on `founders.current_challenges`, and the option list lives
#: in `frontend/src/data/onboardingQuestions.js` ("Fundraising", offered on both
#: onboarding paths). If that label is ever reworded this is the single place to
#: follow it.
#:
#: Compared as a whole stripped label, case-insensitively -- never as a
#: substring. "Fundraising timeline" is not this option, and matching it would
#: make the gate depend on free text a founder typed.
FUNDRAISING_CHALLENGE = "Fundraising"


def _stated_challenges(founder: Any) -> list[str] | None:
    """The challenges the founder explicitly picked, or None when we cannot tell.

    None is the UNKNOWN verdict and is returned for every shape that is not a
    non-empty list of non-empty strings: NULL, `[]`, a bare string, a dict, a
    list of nulls. All of those mean the same thing operationally -- onboarding
    did not give us a usable answer -- and none of them is evidence about what
    this founder is or is not doing.
    """
    raw = getattr(founder, "current_challenges", None)
    if not isinstance(raw, list):
        return None
    picked = [str(v).strip() for v in raw if isinstance(v, str) and str(v).strip()]
    return picked or None


def context_tokens(founder: Any) -> frozenset[str] | None:
    """The context tokens this founder satisfies, or None when unknown.

    None means FAIL OPEN and is the return for any founder whose onboarding
    answer we cannot read. The asymmetry is the whole point of the design:

      * ticking "Fundraising" is an unambiguous statement of intent, so the
        POSITIVE case is trustworthy;
      * NOT ticking it is weak evidence at best -- the question is "biggest
        challenge, pick up to three", so a founder mid-raise who is more worried
        about sales will not tick it. Nothing in the schema means "bootstrapped".

    So the negative case is honoured only when the founder actually answered the
    question, and never inferred from an empty or unreadable one. A stronger
    negative needs an explicit fundraising-status field; this reads the signal
    that already exists rather than adding an onboarding question.

    Never raises. A gate that can throw would be able to end a founder's
    diagnosis over a malformed profile row, which is strictly worse than asking
    a question about investors.
    """
    try:
        picked = _stated_challenges(founder)
    except Exception:                                      # noqa: BLE001
        logger.warning("Context tokens unavailable; gate fails open",
                       extra={"stage": "context_scope"})
        return None
    if picked is None:
        return None
    wanted = FUNDRAISING_CHALLENGE.casefold()
    if any(choice.casefold() == wanted for choice in picked):
        return frozenset({FUNDRAISING_INTENT})
    return frozenset()


def gated_problem_codes(tokens: frozenset[str] | None) -> frozenset[str]:
    """Problem codes to withhold given the founder's context, possibly empty.

    Empty for an unknown context (`tokens is None`), which is what makes the
    caller's fail-open path a single expression rather than a branch it could
    forget.
    """
    if tokens is None:
        return frozenset()
    return frozenset(
        code for code, required in PROBLEM_PRECONDITIONS.items()
        if required not in tokens
    )
