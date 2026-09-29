"""Stop assuming a Growth-stage founder has investors or a board.

THE DEFECT, found auditing the Growth bank the way the ideation and Validation
ones were audited. Twenty questions there name investors or a board. Seven sit
under Fundraising problems and are already withheld from a founder who has not
said they are raising -- `context_scope` does that, and does it well. The other
thirteen are filed under Product, Sales, Financial Management, Founder
Psychology and Scaling, where nothing gates them, so a bootstrapped founder is
asked how they report to a board they do not have:

    SCL-231      Do you ever soften or hold back difficult news when reporting
                 to your board?
    S10-PRD-018  If your board asked, could you show data to justify every
                 major item in this quarter's product plan?
    S10-FIN-076  Has a talk with your board or investors about runway ever
                 shown their number differs from yours?

Most founders this product serves have never raised. They answer nothing, and
the blank scores as a gap.

REWORDED, NOT GATED, and that is the whole decision here.

A gate would need a fact nobody has: whether a founder has investors. It cannot
be borrowed from `FUNDRAISING_INTENT`, which says they are raising or want to
-- a founder who raised years ago and never will again has a board and no
intent, and one preparing a first round has intent and no board. So gating
would have meant a new onboarding question, and then withholding these
questions from the majority who answered no.

But read what the thirteen actually ask. Not one is about a board. They ask
whether the founder softens bad news, whether they can justify a plan with
data, whether anyone outside their own head checks their numbers, whether
silence gets filled with assumptions. Every one of those is true of a founder
with no investors -- the board was scenery, and it was the only part that
excluded anyone. Removing it makes the question reach everybody AND asks the
better question, which is the opposite trade to withholding it from most of
the bank's audience.

So: eleven reworded to drop the board, two left exactly as they are.

    S10-NGO-007  Does your board have the financial or legal skills the
    S10-NGO-008  organisation now needs? / How often does your board actually
                 meet?

Those two are the NGO industry set, and a registered non-profit has a board or
a trustee body by law. There the premise is not scenery -- it is the subject,
and it is true of every founder who can be asked it.

S10-SAS-106-1 "What did your last round buy, and did it buy it?" is the one
that could not lose its premise, because the premise IS the question. It is
made conditional instead, so a founder who has never raised has something true
to say rather than a blank.

Revision ID: f0b82e4d5a19
Revises: a6f3d2c81b47
Create Date: 2026-09-30 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f0b82e4d5a19"
down_revision: Union[str, Sequence[str], None] = "a6f3d2c81b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (code, exact old text, new text). Matched on the full old string, so a
#: question someone has already reworded is left alone rather than overwritten
#: -- the plain-language pass edits this same column.
_REWORD: tuple[tuple[str, str, str], ...] = (
    (
        "PSY-052",
        "Is there something happening now that you are actively hiding from your investors or board (the people who oversee the company)?",
        "Is there something happening right now that you are actively keeping from the people you answer to?",
    ),
    (
        "S10-FIN-076",
        "Has a talk with your board or investors about runway (how many months your money will last) ever shown their number differs from yours?",
        "Has a talk about how long your money will last ever shown that someone else's number was different from yours?",
    ),
    (
        "S10-GTM-044",
        "What evidence would convince your board this market can support the scale you're promising?",
        "What evidence would convince a doubtful outsider that this market is big enough for the growth you are promising?",
    ),
    (
        "S10-PRD-018",
        "If your board asked, could you show data to justify every major item in this quarter's product plan?",
        "If someone asked you to justify every big item in this quarter's product plan, could you show real numbers?",
    ),
    (
        "S10-PRD-069",
        "Do your board or investors ask for numbers on product reliability, and if so, are you confident in the answers you give them?",
        "Does anyone outside your team ask you for numbers on how reliable the product is, and are you confident in what you tell them?",
    ),
    (
        "S10-SAL-028",
        "Does your board regularly see a number showing how much of your revenue depends on your biggest customers, or has nobody formally tracked this?",
        "Do you regularly look at a number showing how much of your income depends on your biggest customers, or has nobody tracked it?",
    ),
    (
        "S10-SAS-106-1",
        "What did your last round buy, and did it buy it?",
        "If you have raised money, what was the last round meant to buy, and did it buy it?",
    ),
    (
        "S10-SLX-070",
        "Does your board or leadership see consistent sales reporting, or does that vary based on who compiles it?",
        "Does anyone besides you see the same sales figures each time, or do they change depending on who puts them together?",
    ),
    (
        "S10-SLX-077",
        "Has a poor view of your deals in progress ever led to a sales forecast that surprised your board or investors?",
        "Has a poor view of the deals you have in progress ever led to a sales forecast that surprised you or anyone relying on it?",
    ),
    (
        "SCL-231",
        "Do you ever soften or hold back difficult news when reporting to your board?",
        "Do you ever soften or hold back bad news when you tell people how the business is really doing?",
    ),
    (
        # Not in the Growth bank at all -- the consistency check at the end of
        # upgrade() found it in the Validation one. "or co-founders" softens
        # the premise without removing it: a founder working alone has neither.
        "FIN-138",
        "If your board or co-founders asked to see your latest numbers right now, would you have something ready to share?",
        "If someone asked to see your latest numbers right now, would you have something ready to share?",
    ),
    (
        "SCL-236",
        "When updates go quiet for a while, do you think your investors might start assuming the worst?",
        "When you go quiet for a while, do you think the people counting on you start assuming the worst?",
    ),
)

#: Left exactly as they are: a registered non-profit has a board by law, so the
#: premise is the subject rather than scenery. Named here so a later reader can
#: see they were considered.
_LEFT_ALONE: tuple[tuple[str, str], ...] = (
    ("S10-NGO-007", "NGO industry set -- a non-profit board is required by law"),
    ("S10-NGO-008", "NGO industry set -- a non-profit board is required by law"),
)


def upgrade() -> None:
    bind = op.get_bind()

    done = 0
    for code, old, new in _REWORD:
        n = bind.execute(
            sa.text(
                "UPDATE questions SET question_text = :new "
                "WHERE question_code = :code AND question_text = :old"
            ),
            {"new": new, "old": old, "code": code},
        ).rowcount
        if n:
            done += n
        else:
            print(f"[{revision}] WARNING {code} did not match its expected "
                  "wording and was left alone")
    print(f"[{revision}] {done} of {len(_REWORD)} questions no longer assume a board")
    for code, why in _LEFT_ALONE:
        print(f"[{revision}]   kept: {code} -- {why}")

    # Whatever still names a board must be either the NGO pair or a Fundraising
    # question, which context_scope already withholds from a founder who has
    # not said they are raising.
    stray = bind.execute(
        sa.text(
            """
            SELECT q.question_code FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE q.question_text ~* '(your board|your investors)'
              AND q.question_code <> ALL(:kept)
              AND p.problem_code NOT LIKE 'FND-%'
            ORDER BY q.question_code
            """
        ),
        {"kept": [code for code, _ in _LEFT_ALONE]},
    ).scalars().all()
    if stray:
        print(f"[{revision}] NOTE still naming a board outside Fundraising: {stray}")


def downgrade() -> None:
    bind = op.get_bind()
    for code, old, new in _REWORD:
        bind.execute(
            sa.text(
                "UPDATE questions SET question_text = :old "
                "WHERE question_code = :code AND question_text = :new"
            ),
            {"old": old, "new": new, "code": code},
        )
