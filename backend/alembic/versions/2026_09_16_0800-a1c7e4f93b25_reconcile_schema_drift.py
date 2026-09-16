"""Reconcile schema applied to the database but never written as a migration.

FOUND BY REBUILDING. `scripts/dump_reference_data.py` produced a dump of every
reference table; loading it into a database built from `alembic upgrade head`
failed on six of them, and the reason was not the data:

    column "embedding_model" of relation "archetypes" does not exist
    column "embedding_model" of relation "behaviour_patterns" does not exist
    column "embedding_dimension" of relation "founder_dna_questions" does not exist
    column "secondary_root_cause_ids" of relation "interventions" does not exist
    relation "support_bot_answers" does not exist
    value too long for type character varying(50)      [scoring_rules.source_document]

All six exist in the live database. None of them was ever written as a
migration, so `alembic upgrade head` has been producing a schema that
production does not have -- and nobody noticed, because nobody had rebuilt
from scratch. The seeded question bank made the attempt fail earlier, at
63340a6e5fdb, and hid everything behind it.

This is the reconciliation. Everything here is transcribed from the live
schema, not designed: same types, same nullability, same defaults.

WHY IT MATTERS BEYOND THE RESTORE. `alembic revision --autogenerate` compares
the models against the database it is pointed at. Run against production it
would have seen these as already present and said nothing; run against a
rebuilt database it would have proposed dropping them. Either way the drift
propagates. Closing it makes head and production the same shape again.

Idempotent throughout (IF NOT EXISTS / IF EXISTS), so it is safe against the
live database, which already has all of it, and against a fresh one, which has
none of it.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1c7e4f93b25"
down_revision: Union[str, Sequence[str], None] = "8c16e1d37f13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Embedding provenance, carried beside every embedded table. questions,
#: problems and root_causes got these in an earlier migration; these three
#: were given them directly in the database and skipped.
_EMBEDDING_METADATA = ("archetypes", "behaviour_patterns", "founder_dna_questions")


def upgrade() -> None:
    for table in _EMBEDDING_METADATA:
        op.execute(f'alter table "{table}" add column if not exists embedding_model text')
        op.execute(f'alter table "{table}" add column if not exists embedding_version text')
        op.execute(f'alter table "{table}" add column if not exists embedding_dimension integer')

    op.execute("alter table interventions add column if not exists "
               "secondary_root_cause_ids jsonb not null default '[]'::jsonb")

    # The live value "Root Cause Ranking Formula (detection focusing --
    # provisional)" is 60 characters; the column was varchar(50), so the dump
    # of the live row would not load into a rebuilt database.
    op.execute("alter table scoring_rules alter column source_document type text")

    op.execute("""
        create table if not exists support_bot_answers (
            question_id   integer      primary key,
            group_number  smallint     not null,
            group_slug    text         not null,
            group_title   text         not null,
            question      text         not null,
            answer        text,
            answer_type   text         not null default 'walked'::text,
            status        text         not null default 'answered'::text,
            is_published  boolean      not null default false,
            blocked_by    text,
            links         text[]       not null default '{}'::text[],
            verified_on   date,
            verified_how  text,
            finding       text,
            note          text,
            source_file   text,
            created_at    timestamptz  not null default now(),
            updated_at    timestamptz  not null default now()
        )
    """)


def downgrade() -> None:
    """Reversible, but note that dropping these loses data in the live
    database. It exists so the revision is well-formed, not because running it
    against production would ever be a good idea."""
    op.execute("drop table if exists support_bot_answers")
    op.execute("alter table interventions drop column if exists secondary_root_cause_ids")
    for table in _EMBEDDING_METADATA:
        for column in ("embedding_model", "embedding_version", "embedding_dimension"):
            op.execute(f'alter table "{table}" drop column if exists {column}')
    # source_document is deliberately NOT narrowed back: values longer than 50
    # characters exist, and truncating them to reverse a widening is worse than
    # leaving the column wide.
