"""One team-size answer above 25, instead of two that behave identically.

Onboarding offered "26-50 people" and "More than 50 people". Nothing in the
question bank distinguishes a thirty-person company from a sixty-person one --
b93f5c07d2e1 said so and declined to invent a line -- so the two answers
produced the same diagnosis. Asking a founder to choose between them was asking
for precision we do not use.

The five bands are now: solo, 2_5, 6_10, 11_25, 26_plus.

WHY A NEW VALUE RATHER THAN REUSING '26_50'. Reusing it would have been a
smaller change and a dishonest one: a founder with two hundred employees would
have a profile that says their team is 26 to 50 people. `team_size` is read by
more than the question filter -- it is on the founder's profile and in the
report's own picture of the business -- so the stored value has to be true.
'26_plus' says exactly what the founder answered.

THE OLD VALUES STAY IN THE CHECK, and that is deliberate. Dropping them would
make the constraint reject a write from the old frontend, and during a deploy
the old bundle is still being served for a few minutes after the migration
runs. A founder finishing onboarding in that window would get a 500 on the last
question of their profile. Keeping the two values accepted costs nothing: after
this migration no row holds them, `TeamSize` no longer offers them, so nothing
can put one back except that straggler -- which is the case they exist for.
`team_scope` ranks them alongside '26_plus' so even that straggler is filtered
correctly rather than falling through as unknown.

Revision ID: d71a4e8c3f05
Revises: b93f5c07d2e1
Create Date: 2026-09-29 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d71a4e8c3f05"
down_revision: Union[str, Sequence[str], None] = "b93f5c07d2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_BAND = "26_plus"
_REPLACED = ("26_50", "50_plus")

#: What the CHECKs allow after this: the five bands a founder can now pick,
#: plus the two they no longer can. See the note above on why the old two stay.
_ALLOWED: tuple[str, ...] = ("solo", "2_5", "6_10", "11_25", _NEW_BAND, *_REPLACED)

_FOUNDERS_CHECK = "founders_team_size_check"
_QUESTIONS_CHECK = "questions_min_team_size_check"


def _values(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    bind = op.get_bind()

    # Widen both CHECKs BEFORE writing the new value, or the updates below
    # violate the constraint they are being migrated into.
    op.drop_constraint(_FOUNDERS_CHECK, "founders", type_="check")
    op.create_check_constraint(
        _FOUNDERS_CHECK, "founders", f"team_size IN ({_values(_ALLOWED)})"
    )
    op.drop_constraint(_QUESTIONS_CHECK, "questions", type_="check")
    op.create_check_constraint(
        _QUESTIONS_CHECK, "questions",
        f"min_team_size IS NULL OR min_team_size IN ({_values(_ALLOWED)})",
    )

    moved = bind.execute(
        sa.text(
            "UPDATE founders SET team_size = :new WHERE team_size = ANY(:old)"
        ),
        {"new": _NEW_BAND, "old": list(_REPLACED)},
    ).rowcount
    print(f"[{revision}] {moved} founder(s) moved to '{_NEW_BAND}'")

    retagged = bind.execute(
        sa.text(
            "UPDATE questions SET min_team_size = :new WHERE min_team_size = ANY(:old)"
        ),
        {"new": _NEW_BAND, "old": list(_REPLACED)},
    ).rowcount
    print(f"[{revision}] {retagged} question(s) now require '{_NEW_BAND}'")

    left = bind.execute(
        sa.text(
            "SELECT count(*) FROM founders WHERE team_size = ANY(:old)"
        ),
        {"old": list(_REPLACED)},
    ).scalar_one() + bind.execute(
        sa.text(
            "SELECT count(*) FROM questions WHERE min_team_size = ANY(:old)"
        ),
        {"old": list(_REPLACED)},
    ).scalar_one()
    if left:
        raise RuntimeError(f"{left} row(s) still hold a retired team-size band")

    for band, n in bind.execute(
        sa.text(
            "SELECT coalesce(min_team_size, '(none)'), count(*) FROM questions "
            "GROUP BY 1 ORDER BY 2 DESC"
        )
    ).all():
        print(f"[{revision}]   {band}: {n}")


def downgrade() -> None:
    bind = op.get_bind()

    # '26_plus' covers everyone above 25, and which side of 50 they sat on was
    # never recorded. '26_50' is the honest reversal: it is the band the
    # questions carried before, and the one a founder in that range would have
    # picked. A founder with two hundred people reverts to a wrong value, which
    # is the cost of going back to a split the data cannot reconstruct.
    bind.execute(
        sa.text("UPDATE founders SET team_size = '26_50' WHERE team_size = :new"),
        {"new": _NEW_BAND},
    )
    bind.execute(
        sa.text("UPDATE questions SET min_team_size = '26_50' WHERE min_team_size = :new"),
        {"new": _NEW_BAND},
    )

    original = ("solo", "2_5", "6_10", "11_25", "26_50", "50_plus")
    op.drop_constraint(_FOUNDERS_CHECK, "founders", type_="check")
    op.create_check_constraint(
        _FOUNDERS_CHECK, "founders", f"team_size IN ({_values(original)})"
    )
    op.drop_constraint(_QUESTIONS_CHECK, "questions", type_="check")
    op.create_check_constraint(
        _QUESTIONS_CHECK, "questions",
        f"min_team_size IS NULL OR min_team_size IN ({_values(original)})",
    )
