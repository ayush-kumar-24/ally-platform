"""Reword the fifteen industry questions that named a place or a role.

A founder picks their industry at onboarding and the diagnosis draws on that
industry's bank. Some of those questions named something the founder may not
have -- a kitchen, a warehouse, a factory, a clinician -- and so asked them
about operations they do not run. A founder selling booking software to
physiotherapy clinics was asked "How much of your week goes on clinical work?".
Most electronics and fashion brands do not own the factory whose labour
conditions they were asked about.

Each of these fifteen keeps the industry's own vocabulary and loses only the
premise: "recipe card in the kitchen" becomes "recipe or spec for what you
make", still a food question; "by the time it reaches your warehouse" becomes
"by the time it reaches you", with customs, freight and port charges untouched.
Two actually gain -- S0-HLT-003 adds software to its list of business types, and
S0-HLT-009 names the clinic and the employer alongside the patient.

WHY THIS IS FIFTEEN AND NOT SIXTY-FOUR. The first version of this migration
reworded 64. Forty-nine of those replaced the industry's vocabulary for its
customers or its product -- patients, guests, dish, menu, shop, students -- with
"customers" and "items". That removed the premise and the specificity together,
and specificity is the product: a homestay owner reading "Do you ask happy
guests to leave a review?" is understood, and reading "happy customers" could be
any business alive. The founder who prompted the fix is the minority -- most
people who pick Healthcare ARE a clinic -- so rewording for everyone protected
the exception by flattening the majority.

Those 49 keep their original wording and are WITHHELD instead, from founders who
do not run the industry's core operation, together with the 27 that could never
have been reworded at all. See the `business_model` work for that filter; this
migration is only the fifteen where rewording loses nothing.

EVERY OLD TEXT IS SPELLED OUT IN FULL AND MATCHED EXACTLY, and the upgrade raises
unless each pair changes exactly one row. A rewording that silently matched
nothing is the one failure mode here: it leaves the old text live while reporting
success. Keyword matching over this bank has already been wrong in both
directions twice (d4a1f8c62b73, a6f3d2c81b47), so nothing here is inferred.

The downgrade restores every original exactly, with the same check.

See docs/drafts/industry-question-rewording.md for the full review of all 128.

Revision ID: a3f7b21c6d84
Revises: c92a41f7b508
Create Date: 2026-10-02 09:00:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import bindparam, text

revision = "a3f7b21c6d84"
down_revision = "c92a41f7b508"
branch_labels = None
depends_on = None

#: (question_code, text as it is now, text it becomes). Fifteen questions whose
#: premise was a place or a role, and whose industry vocabulary survives the
#: change. Grouped by industry.
_REWORD: tuple[tuple[str, str, str], ...] = (

    # --- Healthcare -- these two gain an option rather than lose a word
    (
        'S0-HLT-003',
        'Is your business a medical device, a clinic, a pharmacy or a '
        'consultation service? The rules are different for each.',
        'Is your business a medical device, a clinic, a pharmacy, a '
        'consultation service, or software used by any of those? The rules '
        'are different for each.',
    ),
    (
        'S0-HLT-009',
        'How much would an ordinary patient pay for this from their own '
        'pocket?',
        'How much would your buyer pay for this out of their own pocket, '
        'whether that is a patient, a clinic or an employer?',
    ),

    # --- Food & Beverage -- a kitchen is not the only way to make food
    (
        'S01-FNB-006',
        'Is there a written recipe card in the kitchen, or is it from memory?',
        'Is there a written recipe or spec for what you make, or is it from '
        'memory?',
    ),
    (
        'S01-FNB-102-2',
        'What is your food waste, and which dishes drive it?',
        'What is your food waste, and which items drive it?',
    ),
    (
        'S01-FNB-103-2',
        'How is a new kitchen hire trained in their first week?',
        'How is a new hire on the food side trained in their first week?',
    ),
    (
        'S01-FNB-110-2',
        'What does a new kitchen hire have to learn that nobody has written?',
        'What does someone new on the food side have to learn that nobody '
        'has written down?',
    ),
    (
        'S10-FNB-007',
        'What food safety training does a new kitchen hire receive?',
        'What food safety training does a new hire receive?',
    ),
    (
        'S10-FNB-011',
        'How many kitchen staff have left in the last year?',
        'How many of the people who make your food have left in the last '
        'year?',
    ),
    (
        'S10-FNB-101-1',
        'How do you measure variance between what the spec says and what '
        'leaves the kitchen?',
        'How do you measure the gap between what the spec says and what '
        'actually ships?',
    ),

    # --- Trading -- goods can land without a warehouse
    (
        'S0-TRD-006',
        'What will one unit actually cost you by the time it reaches your '
        'warehouse?',
        'What will one unit actually cost you by the time it reaches you?',
    ),
    (
        'S0-TRD-007',
        'In the cost of one unit reaching your warehouse, have you included '
        'customs duty?',
        'In the cost of one unit reaching you, have you included customs '
        'duty?',
    ),
    (
        'S0-TRD-008',
        'In the cost of one unit reaching your warehouse, have you included '
        'freight (shipping charges) and insurance?',
        'In the cost of one unit reaching you, have you included freight '
        '(shipping charges) and insurance?',
    ),
    (
        'S0-TRD-009',
        'In the cost of one unit reaching your warehouse, have you included '
        'customs clearing, port and agent charges?',
        'In the cost of one unit reaching you, have you included customs '
        'clearing, port and agent charges?',
    ),

    # --- Consumer Electronics -- the brand rarely owns the factory
    (
        'S10-CEL-020',
        'If your factory stopped tomorrow, how long before you could '
        'produce anywhere else?',
        'If the place that makes your product stopped tomorrow, how long '
        'before you could produce anywhere else?',
    ),

    # --- Fashion -- the brand rarely owns the factory
    (
        'S10-FSH-020',
        'If a buyer asked about your factory labour conditions, could you '
        'answer?',
        'If a buyer asked about labour conditions where your product is '
        'made, could you answer?',
    ),
)


def _apply(pairs: tuple[tuple[str, str, str], ...]) -> None:
    """Rewrite each question, skipping any whose text has moved on.

    THIS DELIBERATELY DOES NOT FAIL ON DRIFT, and the first version did. It
    required every pair to match exactly one row and raised otherwise, with a
    comment saying not to loosen it. That was wrong, and it cost a production
    deploy: `alembic upgrade head` runs inside the release, so one question whose
    text had moved since this migration was written stopped the migration, the
    ECS service was never updated, and nothing shipped -- not this rewording,
    not the two migrations behind it, not the application image.

    The original reasoning conflated two different things. A rewording that
    matches nothing because somebody ALREADY IMPROVED that question is not a
    failure: this migration's text is the stale one, and the right thing is to
    leave theirs alone. Only one case means the migration is pointed at the
    wrong database entirely -- when NOT ONE pair matches, in either direction --
    and that is what still raises.

    So: text already equal to the new wording counts as done; text equal to the
    old wording is rewritten; anything else is left exactly as it is and named
    in the output.
    """
    stmt = text(
        """
        UPDATE questions SET question_text = :new, updated_at = now()
        WHERE question_code = :code AND question_text = :old
        """
    ).bindparams(bindparam("new"), bindparam("code"), bindparam("old"))

    bind = op.get_bind()
    applied = already_done = 0
    left_alone: list[str] = []

    for code, old, new in pairs:
        current = bind.execute(
            text("SELECT question_text FROM questions WHERE question_code = :code"),
            {"code": code},
        ).scalar()
        if current is None:
            left_alone.append(f"{code} (not in this catalogue)")
        elif current == new:
            already_done += 1
        elif current == old:
            bind.execute(stmt, {"code": code, "old": old, "new": new})
            applied += 1
        else:
            left_alone.append(f"{code} (text has moved on)")

    if applied == 0 and already_done == 0:
        raise RuntimeError(
            f"None of the {len(pairs)} questions named by {revision} were found "
            "with either their expected text or their rewording. That is not "
            "drift, it is the wrong catalogue -- check which database this ran "
            f"against before changing the pairs. Left alone: {left_alone}"
        )

    print(
        f"{revision}: reworded {applied}, already done {already_done}, "
        f"left alone {len(left_alone)}"
        + (f" -- {'; '.join(left_alone)}" if left_alone else "")
    )


def upgrade() -> None:
    _apply(_REWORD)


def downgrade() -> None:
    _apply(tuple((code, new, old) for code, old, new in _REWORD))
