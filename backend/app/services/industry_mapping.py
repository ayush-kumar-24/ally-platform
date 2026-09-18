"""Turning what a founder picked in onboarding into `founders.industry_mapped_id`.

WHY THIS EXISTS. `founders.industry` holds a LABEL a founder chose from a
dropdown; `industries.industry_code` is the catalogue key everything else keys
off. Nothing ever joined the two. `industry_mapped_id` was read in three places
(reasoning context, diagnosis session snapshot, ally context builder) and
written in none, so it was NULL for every founder the application created --
46 of 47 in production on 2026-09-18. Every industry-aware decision downstream
was therefore inert, not wrong: it simply never had an industry to work with.

THIS MODULE IS A VOCABULARY BRIDGE, NOT INDUSTRY LOGIC. It holds one thing the
database cannot: which of the catalogue's codes each onboarding dropdown option
means. No diagnostic behaviour is decided here, and no industry is special-cased
anywhere -- an industry becomes usable by being present in `industries` and
having content tagged to it, never by being named in application code.

THREE VOCABULARIES ARE ALREADY IN THE COLUMN. Measured on production:

    saas                 4 founders   an industry CODE
    AI                   3            an onboarding LABEL
    Agriculture          2            an onboarding LABEL
    Technology & SaaS    1            an industry NAME
    Fintech              1            an onboarding LABEL
    D2C                  1            an onboarding LABEL
    SaaS                 1            an onboarding LABEL

So the resolver accepts all three, in a fixed order, case-insensitively. It is
deliberately NOT fuzzy: no substring matching, no "starts with", no edit
distance. A label we do not recognise resolves to None and is reported, because
guessing an industry silently is worse than leaving it unknown -- unknown fails
open everywhere downstream, a wrong guess filters the founder's questions to
somebody else's industry.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logger import logger

#: Every option in the onboarding industry dropdown
#: (`frontend/src/data/onboardingQuestions.js`, question `industry`), mapped to
#: an `industries.industry_code` -- or to None where mapping it would be a
#: guess. Every option must appear here, including the ones that map to None:
#: `test_industry_mapping.py` fails if the dropdown grows an option this map has
#: not made a decision about, so a new label cannot reach production silently
#: unmapped.
#:
#: The dropdown offers 12 options against a 30-row catalogue, so most founders
#: cannot currently name their real industry at all. Widening the dropdown is a
#: product decision and a separate change; this map covers what it offers today.
#:
#: TWO ENTRIES ARE JUDGEMENT CALLS AND ARE FLAGGED AS SUCH:
#:
#:   'AI' -> saas
#:       The catalogue has no AI row. An AI company could sell into any
#:       vertical, but what onboarding is asking is "what kind of business is
#:       this", and an AI startup is a technology/software business before it
#:       is anything else. Three production founders are on this label, so it
#:       is not hypothetical. Revisit if an `ai` industry is ever seeded.
#:
#:   'D2C' -> ecommerce_d2c
#:       Two rows could take it: `manufacturing` is named "Manufacturing & D2C"
#:       and `ecommerce_d2c` is named "E-commerce & D2C". The former's name is
#:       an artefact of the original four-industry taxonomy, where D2C had
#:       nowhere else to go; the latter was created for exactly this. A D2C
#:       brand that does not manufacture would be badly served by
#:       `manufacturing`, so the specific row wins.
INDUSTRY_LABEL_TO_CODE: dict[str, str | None] = {
    "AI": "saas",                    # judgement call -- see above
    "SaaS": "saas",
    "Fintech": "fintech",
    "Manufacturing": "manufacturing",
    "Healthcare": "healthtech",
    "Education": "edtech",
    "D2C": "ecommerce_d2c",          # judgement call -- see above
    "Services": "services",
    "Logistics": "logistics",
    "Real Estate": "proptech",
    "Agriculture": "agritech",
    # Deliberately unmapped. "Other" is the founder telling us the list does
    # not describe them; the honest record of that is no industry, which reads
    # downstream as UNKNOWN and fails open. Mapping it anywhere would be
    # inventing a fact they declined to give.
    "Other": None,
}

#: The labels above that were a judgement call rather than an obvious match.
#: Surfaced so a reviewer can find them without re-reading the comments, and so
#: a test can assert the list has not quietly grown.
JUDGEMENT_CALLS = frozenset({"AI", "D2C"})

_LABEL_LOOKUP = {label.casefold(): code for label, code in INDUSTRY_LABEL_TO_CODE.items()}


def resolve_industry_code(label: Any) -> str | None:
    """The canonical industry code for an onboarding label, or None.

    Pure and database-free, so the mapping itself is unit-testable. Only the
    explicit dropdown map is consulted here -- code and name matching need the
    catalogue and live in `resolve_industry_id`.
    """
    if not isinstance(label, str):
        return None
    cleaned = label.strip()
    if not cleaned:
        return None
    return _LABEL_LOOKUP.get(cleaned.casefold())


def resolve_industry_id(db: Session, label: Any) -> int | None:
    """`industries.industry_id` for whatever is in `founders.industry`, or None.

    Resolution order, first hit wins, all case-insensitive:

      1. the onboarding dropdown map above      ('Agriculture' -> agritech)
      2. an exact `industries.industry_code`    ('saas')
      3. an exact `industries.industry_name`    ('Technology & SaaS')

    Steps 2 and 3 exist because the column already holds all three shapes (see
    the module docstring) -- they are for the rows history left behind, not for
    anything onboarding writes today.

    Returns None for an unrecognised label, and logs it at INFO so the set of
    unmapped labels is discoverable from logs rather than by querying founders.
    Never raises: an industry that cannot be resolved must not be able to fail a
    profile save.
    """
    if not isinstance(label, str) or not label.strip():
        return None
    cleaned = label.strip()

    code = resolve_industry_code(cleaned)
    try:
        if code is not None:
            row = db.execute(
                text("SELECT industry_id FROM industries WHERE lower(industry_code) = :c"),
                {"c": code.lower()},
            ).scalar()
            if row is not None:
                return int(row)
            # The map named a code the catalogue does not have. That is a data
            # problem worth seeing -- a seeded industry was renamed or removed
            # out from under this map -- not something to paper over.
            logger.warning(
                "industry label maps to a code that is not in the catalogue",
                extra={"stage": "industry_mapping", "label": cleaned, "code": code},
            )
            return None

        row = db.execute(
            text(
                "SELECT industry_id FROM industries "
                "WHERE lower(industry_code) = :v OR lower(industry_name) = :v"
            ),
            {"v": cleaned.casefold()},
        ).scalar()
        if row is not None:
            return int(row)
    except Exception as exc:  # noqa: BLE001 -- a lookup must never fail a save
        logger.warning(
            "industry lookup failed; leaving industry_mapped_id unchanged",
            extra={"stage": "industry_mapping", "label": cleaned},
            exc_info=exc,
        )
        return None

    logger.info(
        "industry label has no canonical mapping",
        extra={"stage": "industry_mapping", "label": cleaned},
    )
    return None


def unmapped_labels(labels: Any) -> list[str]:
    """Which of `labels` this module cannot map. For validation and reporting.

    Used by the backfill migration to report what it left behind, and available
    to any data-quality check that wants the same answer without a database.
    """
    if not labels:
        return []
    return sorted({
        label.strip() for label in labels
        if isinstance(label, str) and label.strip() and resolve_industry_code(label) is None
    })
