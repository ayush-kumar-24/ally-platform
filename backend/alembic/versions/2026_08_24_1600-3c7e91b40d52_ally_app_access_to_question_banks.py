"""give ally_app unfiltered access to the two question banks

Revision ID: 3c7e91b40d52
Revises: 8f6c2a1d9b7e

Finishes what 8f6c2a1d9b7e started. 4aa14aee3a4e enabled RLS on 30 tables;
8f6c2a1d9b7e restored `ally_app` access to 28 of them (23 founder-owned and 5
internal) and left the two REFERENCE tables -- current_problem_questions and
founder_dna_questions -- carrying only 4aa's policy:

    FOR SELECT TO public USING (is_active = true)

`public` includes `ally_app`, so the backend can still read ACTIVE questions
and nothing looks wrong in a smoke test. The gap is the inactive ones.

Six queries join these banks deliberately WITHOUT an is_active filter, because
they are about questions a founder has ALREADY ANSWERED -- whether a question
is still offered to new founders has no bearing on what this founder was asked
last week:

    founder_dna/repository.py     answered_history, answers_per_dimension,
                                  closing_answered, recent_qa_for_dimension
    current_problem/repository.py answered_history, count_answered

Under the is_active predicate every one of those silently loses its rows the
moment a question is deactivated, and they fail in ways that do not look like
a permissions problem:

  * answered_history -- the founder's transcript loses those Q&A pairs on
    resume, which reads as the conversation having been wiped.
  * answers_per_dimension -- undercounts, so the engine re-asks a dimension it
    has already covered and dimension_pool_exhausted can never be satisfied.
  * closing_answered -- returns False forever, so select_next_question keeps
    handing back the closing question and the phase never completes.
  * count_answered -- the progress counter sticks ("3 of 4" indefinitely).

Deactivating a single question could therefore wedge a founder's Founder DNA
or Current Problem phase permanently, on RDS only, with no error raised
anywhere. Question banks are edited as content, not as schema, so this is a
routine action rather than a hypothetical one.

The fix matches 8f6c2a1d9b7e's shape exactly: an ADDITIVE permissive policy
scoped TO ally_app, alongside 4aa's public one rather than replacing it.
Permissive policies OR together, so direct PostgREST clients keep seeing only
active questions while the backend role sees the whole bank.

USING (true), not a narrower predicate: these tables are the question CONTENT,
carry no founder column and no tenant concept, and RLS on them exists to keep
Supabase's auto-generated API from serving them, not to limit this backend.
That is the same reasoning 8f6c2a1d9b7e applied to INTERNAL_TABLES.

FOR ALL rather than FOR SELECT. The banks are seeded by migrations running as
the owner, so the backend does not write them today -- but a SELECT-only
policy is exactly the shape that produced this bug, and a future seeding or
admin-editing path would hit the same silent denial. There is nothing to
protect by withholding write access from a role that already has unrestricted
read.

Gated on ally_app like every RLS migration in this project: a no-op on
Supabase, where 4aa's public policy is the whole intent and correct as it
stands.
"""

from alembic import op
from sqlalchemy import text


revision = "3c7e91b40d52"
down_revision = "8f6c2a1d9b7e"
branch_labels = None
depends_on = None


ALLY_APP_ROLE = "ally_app"

#: Distinct from 8f6c2a1d9b7e's two policy names so downgrade() removes only
#: what this migration created.
REFERENCE_POLICY = "ally_runtime_reference_access_v2"

#: The question banks 4aa14aee3a4e classified as REFERENCE.
REFERENCE_TABLES = (
    "current_problem_questions",
    "founder_dna_questions",
)


def _ally_app_exists() -> bool:
    """Whether the RDS-only `ally_app` runtime role exists on this target.
    Duplicated per-migration on purpose -- see the note in 7c4f0f1a9d2e."""
    return bool(
        op.get_bind()
        .execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": ALLY_APP_ROLE},
        )
        .scalar()
    )


def upgrade() -> None:
    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist; "
            "skipping the question-bank runtime policies. EXPECTED on "
            "Supabase, where 4aa14aee3a4e's public is_active policy is the "
            "whole intent."
        )
        return

    for table in REFERENCE_TABLES:
        op.execute(
            f'DROP POLICY IF EXISTS "{REFERENCE_POLICY}" ON public."{table}"'
        )
        op.execute(
            f'CREATE POLICY "{REFERENCE_POLICY}" '
            f'ON public."{table}" '
            "AS PERMISSIVE "
            "FOR ALL "
            f"TO {ALLY_APP_ROLE} "
            "USING (true) "
            "WITH CHECK (true)"
        )


def downgrade() -> None:
    # Mirrors upgrade()'s guard for the same reason 8f6c2a1d9b7e does: on a
    # target without the role there is nothing this migration created, and a
    # DROP POLICY IF EXISTS would still be a no-op -- but the guard keeps the
    # two directions provably symmetric.
    if not _ally_app_exists():
        return

    for table in REFERENCE_TABLES:
        op.execute(
            f'DROP POLICY IF EXISTS "{REFERENCE_POLICY}" ON public."{table}"'
        )
