"""widen founders profile columns to match the API's own limits

PATCH /profile answered 500 for any founder whose profile text was longer than
the column behind it but shorter than the limit the API advertises. Seven
fields on FounderUpdate declare a max_length wider than the varchar they are
written to, so a value in the gap passes Pydantic, reaches Postgres, and raises
StringDataRightTruncation -- an unhandled 500, with the whole update lost.

    field                    API max_length      column
    working_relationship     100                 varchar(30)
    experience_level         100                 varchar(20)
    decision_making_style    100                 varchar(30)
    team_size                 50                 varchar(20)
    current_revenue           50                 varchar(30)
    business_model           100                 varchar(30)
    website                  500                 varchar(300)

Found on 2026-08-19 by a full journey run: "gather everything, then decide
late" is 35 characters of decision_making_style, and saving a profile
containing it failed outright.

The DB is widened to the API's number rather than the API narrowed to the DB's,
because these are prose answers a founder types about themselves and 20-30
characters is not enough to hold one. That direction also keeps the published
contract intact -- narrowing it would turn today's 500 into a 422 for the same
input, which is tidier but still a rejection of a reasonable answer.

Widening a varchar in Postgres is a catalog-only change: no table rewrite, no
ACCESS EXCLUSIVE hold beyond the metadata update, safe on a live table.

Revision ID: c8a1f47b93de
Revises: a7c419d0f2b3
Create Date: 2026-08-19 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8a1f47b93de"
down_revision: Union[str, Sequence[str], None] = "a7c419d0f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (column, new length, old length) -- old is kept so downgrade is exact rather
#: than a guess. Downgrade is only safe while no stored value exceeds the old
#: width, which is why it truncates nothing and will simply fail loudly if one
#: does; losing a founder's words to make a rollback tidy is the wrong trade.
_WIDENED: tuple[tuple[str, int, int], ...] = (
    ("working_relationship", 100, 30),
    ("experience_level", 100, 20),
    ("decision_making_style", 100, 30),
    ("team_size", 50, 20),
    ("current_revenue", 50, 30),
    ("business_model", 100, 30),
    ("website", 500, 300),
)


def upgrade() -> None:
    for column, new_len, _old in _WIDENED:
        op.alter_column(
            "founders",
            column,
            type_=sa.String(length=new_len),
            existing_type=sa.String(length=_old),
            existing_nullable=True,
        )


def downgrade() -> None:
    for column, new_len, old_len in _WIDENED:
        op.alter_column(
            "founders",
            column,
            type_=sa.String(length=old_len),
            existing_type=sa.String(length=new_len),
            existing_nullable=True,
        )
