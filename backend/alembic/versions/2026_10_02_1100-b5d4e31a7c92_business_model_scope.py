"""Withhold the questions written for an operation the founder does not run.

Three founders tick Healthcare: a physiotherapy clinic, a medical device maker,
and somebody selling booking software to clinics. They share one question bank,
and 21 of its questions are written for the first only -- "Out of 100 patients,
how many use you a second time?", "How much of your week goes on clinical
work?". The same split runs through twelve industries, and Food & Beverage is
the largest at 29: a restaurant, a packaged-food maker and a kitchen-software
company all pick it.

WHY NOT REWORDED. a3f7b21c6d84 first reworded 64 of these -- patients became
customers, guests became customers, dish and menu became item and range. It
worked and it was wrong. Specificity is the product: a homestay owner reading
"Do you ask happy guests to leave a review?" is understood, and reading "happy
customers" could be any business alive. And the founder who prompted the fix is
the minority -- most people who pick Healthcare ARE a clinic -- so rewording for
everybody protected the exception by flattening the majority. Fifteen rewordings
stand, where the premise was a PLACE or a ROLE and the industry's vocabulary
survived losing it. The other 49 have their original wording back and are tagged
here instead.

TWO FLAGS, NOT ONE, AND THE SECOND IS THE HONEST PART.

  `requires_operating_role` (71) -- the subject is the industry's own operation:
  a kitchen, a clinical rota, a fleet, patients, guests. 49 reverted rewordings
  plus 22 that could never have been reworded, because their subject really is
  a kitchen and no neutral noun keeps them meaningful.

  `requires_multiple_locations` (5) -- the subject is a SECOND site. These are
  withheld on the same signal today, because a software company has no sites at
  all, but the signal is not the right one: a single-outlet restaurant runs the
  operation and still has no second site. A separate flag means that the day a
  location count is collected, these five can be gated properly without
  disturbing the other 71. One flag would have hidden that distinction, and it
  would have been found by a founder, not by us.

EVERY CODE IS LISTED EXPLICITLY and the upgrade raises unless it tags exactly as
many rows as it names. Keyword screening over this bank has been wrong in both
directions twice (d4a1f8c62b73, a6f3d2c81b47); these 76 come from reading all
128 flagged questions one at a time, recorded in
docs/drafts/industry-question-rewording.md.

Revision ID: b5d4e31a7c92
Revises: a3f7b21c6d84
Create Date: 2026-10-02 11:00:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "b5d4e31a7c92"
down_revision = "a3f7b21c6d84"
branch_labels = None
depends_on = None

#: The subject is the industry's own operation -- a kitchen, a clinical rota, a
#: fleet, patients, guests. Asked only of a founder who runs one.
_REQUIRES_OPERATING_ROLE: tuple[str, ...] = (
    "S0-DLV-304-1", "S0-ECM-006", "S0-ECM-009", "S0-EDU-304-1",
    "S0-FNB-006", "S0-FNB-102-1", "S0-FNB-102-2", "S0-FNB-104-1",
    "S0-FNB-104-2", "S0-FNB-301-1", "S0-FNB-303-2", "S0-FNB-306-2",
    "S0-HLT-302-1", "S0-RTL-307-1", "S0-TRV-005", "S0-TRV-007",
    "S0-TRV-303-2", "S01-DLV-006", "S01-DLV-010", "S01-DLV-013",
    "S01-FNB-019", "S01-FNB-102-1", "S01-FNB-104-2", "S01-FNB-110-1",
    "S01-FNB-301-2", "S01-FNB-302-2", "S01-FNB-303-2", "S01-HLT-006",
    "S01-HLT-007", "S01-HLT-008", "S01-HLT-009", "S01-HLT-010",
    "S01-HLT-011", "S01-HLT-014", "S01-HLT-015", "S01-HLT-016",
    "S01-HLT-017", "S01-HLT-018", "S01-LOG-009", "S01-LOG-012",
    "S01-RTL-008", "S01-TRV-004", "S01-TRV-010", "S01-TRV-012",
    "S01-TRV-016", "S01-TRV-302-1", "S10-CEL-005", "S10-DLV-306-1",
    "S10-ECM-003", "S10-EDU-307-1", "S10-FNB-006", "S10-FNB-020",
    "S10-FNB-023", "S10-FNB-102-1", "S10-FNB-102-2", "S10-HLT-002",
    "S10-HLT-003", "S10-HLT-005", "S10-HLT-015", "S10-HLT-302-2",
    "S10-HLT-303-1", "S10-HLT-305-1", "S10-LOG-011", "S10-LOG-306-1",
    "S10-RTL-301-1", "S10-RTL-303-2", "S10-RTL-304-1", "S10-RTL-304-2",
    "S10-TRV-013", "S10-TRV-015", "S10-TRV-305-1",
)

#: The subject is a SECOND site. Flagged apart from the above because the signal
#: that gates them today is a stand-in, not the real fact: see the docstring.
_REQUIRES_MULTIPLE_LOCATIONS: tuple[str, ...] = (
    "S10-FNB-004", "S10-FNB-307-2", "S10-TRV-004", "S10-PRP-203-1",
    "S10-PRP-206-2",
)


def _set(column: str, codes: tuple[str, ...], value: bool) -> None:
    """Flip `column` for these codes, skipping any the catalogue does not have.

    THIS DELIBERATELY DOES NOT FAIL ON A MISSING CODE, and the first version
    did: it required the update to touch exactly as many rows as it named, and
    raised otherwise. That cost a production deploy. `alembic upgrade head` runs
    inside the release, so one renamed or removed question stops the migration,
    the ECS service is never updated, and nothing ships at all -- not the tags,
    not the application image.

    A question this migration cannot find is a question that cannot be asked
    either, so failing to tag it withholds nothing from nobody. The case that
    still raises is the one meaning this ran against the wrong catalogue
    entirely: not one of the codes present.
    """
    bind = op.get_bind()
    present = {
        row[0]
        for row in bind.execute(
            text("SELECT question_code FROM questions WHERE question_code = ANY(:codes)"),
            {"codes": list(codes)},
        ).all()
    }
    missing = sorted(set(codes) - present)

    if not present:
        raise RuntimeError(
            f"None of the {len(codes)} questions {column} names are in this "
            "catalogue. That is not drift, it is the wrong database -- check "
            "which one this ran against before editing the list in b5d4e31a7c92."
        )

    bind.execute(
        text(
            f"UPDATE questions SET {column} = :value, updated_at = now() "
            "WHERE question_code = ANY(:codes)"
        ),
        {"value": value, "codes": sorted(present)},
    )

    print(
        f"b5d4e31a7c92: {column} set on {len(present)} of {len(codes)}"
        + (f"; not in this catalogue: {', '.join(missing)}" if missing else "")
    )


def upgrade() -> None:
    for column in ("requires_operating_role", "requires_multiple_locations"):
        op.execute(
            f"ALTER TABLE questions ADD COLUMN IF NOT EXISTS {column} "
            "BOOLEAN NOT NULL DEFAULT false"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_questions_{column} "
            f"ON questions ({column}) "
            f"WHERE {column}"
        )

    _set("requires_operating_role", _REQUIRES_OPERATING_ROLE, True)
    _set("requires_multiple_locations", _REQUIRES_MULTIPLE_LOCATIONS, True)


def downgrade() -> None:
    # Dropping each column takes its index and all of its tags with it, and the
    # tags are the whole of this migration's data, so there is nothing to
    # preserve separately.
    for column in ("requires_operating_role", "requires_multiple_locations"):
        op.execute(f"ALTER TABLE questions DROP COLUMN IF EXISTS {column}")
