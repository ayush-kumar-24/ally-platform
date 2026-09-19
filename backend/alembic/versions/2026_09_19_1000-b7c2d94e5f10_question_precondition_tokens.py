"""question_tags.precondition_token, and the first conservative curation.

WHY A COLUMN AND NOT A CODE TABLE. Applicability is CONTENT, not logic. "An HR
tooling question presupposes employees" is an editorial judgement about the
question bank, and the bank is Arya's. Putting it in `question_tags` means a new
precondition is a data change, and the engine needs no release to honour it --
the same property industry eligibility already has.

WHY ONLY THREE TAGS. Every tag was read before this was written; only three are
semantically pure enough to gate on. `hr-capability`, `hr-process` and
`hr-tooling` are 91 distinct questions, all of them `Stage 1->10+`, all in
`Team & Leadership`, under exactly two problems (TM-006 Cultural and
Communication Problems, TM-077 No People Systems or HR Tooling). Their text is
uniformly about people who are not the founder -- "every manager on your team",
"performance reviews", "manual payroll processing as headcount has grown". A
founder who has stated `team_size = 'solo'` cannot answer any of them.

WHAT WAS DELIBERATELY NOT TAGGED, and why, so this is not re-litigated:

  sales-team-capability (60)   MIXED. Contains "If you had to hire your first
                               real salesperson tomorrow, would you know what to
                               look for?" and "Do you know your own close rate?"
                               -- both are FOR a founder without a sales team.
  marketing-team-capability    MIXED, same shape: "Do you know what marketing
  (30)                         capability you're currently missing?" applies to
                               a solo founder exactly as written.
  delegation (53)              A solo founder has delegation READINESS problems.
  hiring (71)                  A solo founder's first hire is the whole point.
  team-communication (165)     Contains "Who has real decision-making authority
                               in this business besides you?" -- the founder-
                               dependency question, which is most acute solo.
  team-expertise (94)          Contains "...on your own?" phrasings.
  fundraising-readiness (101)  All 14 FND-005 questions carry it; tagging it
                               would silently undo the deliberate FND-005
                               carve-out that `context_scope` already makes.
  cofounder-dynamics (29)      Would need a `has_cofounder` family, and nothing
                               on `founders` records one. UNKNOWN is the honest
                               answer, and UNKNOWN keeps the question.

SOLO IS NOT "NO FOUNDER DEPENDENCY". Nothing here gates workload, delegation
readiness, hiring readiness, founder bottleneck or role evolution. A solo
founder is the founder MOST likely to have those problems, and the gate exists
to stop Ally asking about a team that does not exist -- not to stop it asking
about the founder.

Additive and reversible: a nullable column plus three UPDATEs, and the
downgrade clears only the three rows this set. Nothing is deleted, no question
row is touched, and a database where these tags do not exist is a no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "b7c2d94e5f10"
down_revision = "c1b8e05a37f4"
branch_labels = None
depends_on = None

#: tag_name -> precondition token. See the module docstring for the rejections.
#: `has_team` is `founder_context.TOKEN_HAS_TEAM`; the two are asserted equal by
#: tests/test_tag_preconditions.py so this cannot drift into a dead token.
CURATED = {
    "hr-capability": "has_team",
    "hr-process": "has_team",
    "hr-tooling": "has_team",
}


def upgrade() -> None:
    op.add_column(
        "question_tags",
        sa.Column("precondition_token", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "idx_question_tags_precondition",
        "question_tags",
        ["precondition_token"],
        postgresql_where=sa.text("precondition_token IS NOT NULL"),
    )
    conn = op.get_bind()
    for tag_name, token in CURATED.items():
        conn.execute(
            sa.text(
                "UPDATE question_tags SET precondition_token = :token "
                "WHERE tag_name = :tag AND precondition_token IS NULL"
            ),
            {"token": token, "tag": tag_name},
        )


def downgrade() -> None:
    # The column goes, so clearing the rows first would be busywork -- but the
    # index is dropped explicitly because a partial index is not implied by the
    # column drop on every Postgres version.
    op.drop_index("idx_question_tags_precondition", table_name="question_tags")
    op.drop_column("question_tags", "precondition_token")
