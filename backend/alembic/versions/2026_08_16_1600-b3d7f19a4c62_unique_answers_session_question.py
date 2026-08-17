"""add unique constraint on answers(session_id, question_id)

Backstop for a race in DiagnosisService.submit_answer: two near-simultaneous
requests for the same still-current question (double-click, or a client
retry overlapping the original call) could both pass the application-level
"no answer yet" check and both insert -- a duplicate answer row plus a
duplicate LLM advisor call, and the session's current_question_id/
routing_state left inconsistent depending on commit order. submit_answer now
treats the resulting IntegrityError as "resume from the row the other
request already committed" rather than an error, matching the recovery
pattern already used for the pooler-drop case in the same method.

Before adding the constraint, dedupe any rows that already violate it --
this is a live database with real founder answers, so the constraint must
not be added blind. Dedup keeps the earliest row per (session_id,
question_id) (created_at, tie-broken by answer_id) and deletes the rest,
mirroring "the first request to commit wins" -- the same outcome
submit_answer's new recovery path produces going forward.

Revision ID: b3d7f19a4c62
Revises: 6f1d2c9a4b70
Create Date: 2026-08-16 16:00:00.000000

Re-parented 2026-08-17: this was written against a91f4c2d8b17 but never
committed/pushed, so it never actually applied to production. Meanwhile a
separate production-reconciliation effort (PR #17) diverged from the same
a91f4c2d8b17 and was merged as 6f1d2c9a4b70. This migration is unaffected by
that reconciliation (verified live: no uq_answers_session_question-equivalent
index exists on `answers` yet) -- only its parent changes, to keep history
linear on top of the real, now-canonical production lineage.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b3d7f19a4c62'
down_revision: Union[str, Sequence[str], None] = '6f1d2c9a4b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent no-op on a clean table (the expected case -- the
    # application-level check this backstops is not known to have failed in
    # production; this is precautionary, not a response to an observed
    # incident).
    op.execute(
        """
        DELETE FROM answers a
        USING answers b
        WHERE a.session_id = b.session_id
          AND a.question_id = b.question_id
          AND (a.created_at, a.answer_id) > (b.created_at, b.answer_id)
        """
    )
    op.create_index(
        'uq_answers_session_question',
        'answers',
        ['session_id', 'question_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_answers_session_question', table_name='answers')
