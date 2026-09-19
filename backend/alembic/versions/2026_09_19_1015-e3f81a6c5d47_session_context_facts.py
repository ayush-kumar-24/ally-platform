"""session_context_facts -- what a session learned, kept OUT of the profile.

THE DISTINCTION THIS TABLE EXISTS TO ENFORCE. `founders` holds what the founder
STATED about themselves. This holds what one diagnostic session OBSERVED while
asking. They are different kinds of claim and they must not share storage:

  founders.team_size = 'solo'   the founder chose that option in onboarding
  session fact has_team=false   an answer in session 412 read that way

The first is durable and the founder's own. The second is an inference from one
sentence of free text, scoped to the session that heard it. Writing the second
into the first would let a single ambiguous answer silently edit a founder's
record -- and would do it invisibly, because nothing in the product shows the
founder what Ally decided about them.

So facts are session-scoped by primary key and there is deliberately NO path
from this table back to `founders`. `FounderContext.with_session_facts` layers
them on top of a context built from the profile, and profile always wins: a
stated `team_size` is never overridden by an inference. The fact only resolves a
family that was UNKNOWN.

PROVENANCE IS REQUIRED, not decorative. `learned_from_answer_id` is what makes a
fact auditable -- "why did Ally stop asking me about my team?" has an answer
that points at the sentence. It is also what makes the fact retractable if the
answer is ever deleted, hence ON DELETE CASCADE on both parents.

ONE ROW PER (session, token). A later answer about the same token replaces the
earlier verdict rather than accumulating contradictory rows; the unique
constraint is what lets the writer upsert.
"""

from alembic import op
import sqlalchemy as sa

revision = "e3f81a6c5d47"
down_revision = "b7c2d94e5f10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_context_facts",
        sa.Column("fact_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        # The precondition token this fact settles, e.g. 'has_team'. Not
        # constrained to an enum: tokens are data (question_tags.
        # precondition_token) and an unrecognised one degrades to UNKNOWN in
        # founder_context.family_of rather than breaking a session.
        sa.Column("token", sa.String(length=64), nullable=False),
        # The three-valued core is NOT stored here. A fact is only ever recorded
        # when the session established something; "we do not know" is the
        # ABSENCE of a row, which is what keeps UNKNOWN from ever being written
        # down as a denial.
        sa.Column("value", sa.Boolean(), nullable=False),
        sa.Column("learned_from_answer_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("fact_id", name="session_context_facts_pkey"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.session_id"],
            ondelete="CASCADE", name="session_context_facts_session_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["learned_from_answer_id"], ["answers.answer_id"],
            ondelete="CASCADE", name="session_context_facts_answer_id_fkey",
        ),
        sa.UniqueConstraint("session_id", "token", name="uq_session_context_facts"),
    )
    op.create_index(
        "idx_session_context_facts_session", "session_context_facts", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_session_context_facts_session", table_name="session_context_facts")
    op.drop_table("session_context_facts")
