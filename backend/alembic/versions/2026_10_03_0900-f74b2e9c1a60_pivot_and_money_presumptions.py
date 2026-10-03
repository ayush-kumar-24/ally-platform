"""One question that presumes investors, and seventeen that presume a first sale.

Both found by running a real diagnosis as a solo founder at Validation --
pre-revenue, bootstrapped, running spoken-English sessions for students. She was
asked both of these in the same twenty questions.

THE INVESTOR QUESTION. IVA-061, "Do you fear negative reactions from investors
who funded a specific direction you now want to change?". She has no investors.

`context_scope` already withholds investor questions from a founder who has not
said they are raising, and it works: the five other questions in the bank that
name investors all sit under Fundraising problems (FND-001, -002, -004, -006)
and are gated. IVA-061 sits under IVA-005, "Failure to Pivot", in the Idea &
Validation category, so the gate never sees it.

Reworded rather than gated, for the reason f0b82e4d5a19 gives for the twelve
board questions: the question is not about investors. It asks whether fear of
somebody's reaction is stopping a pivot, which is as true of family money, a
co-founder or a customer who vouched for you. The investor was scenery, and it
was the only part that excluded anyone. Gating instead would need the whole of
"Failure to Pivot" gated on fundraising intent, which would withhold nine
questions about pivoting from every bootstrapped founder to fix one.

The sibling question IVA-059 already had the right shape -- "described this idea
to investors OR FAMILY" -- so this makes IVA-061 match a pattern the bank
already uses rather than inventing one.

THE FIFTEEN THAT PRESUME A FIRST SALE. `requires_trading` (a6f3d2c81b47,
e81c47a92f36) withholds a question from a founder who has not sold anything.
Those passes searched for revenue, churn, invoices, renewals, margin. They
missed the questions that say the same thing in different words: "Did your last
batch make money?", "your buyers", "your clients", "your buyers' payment
history".

TWENTY-FOUR WERE FOUND AND NINE ARE NOT HERE, which is the whole reason this is
a list and not a pattern. The tense decides it:

  "Did your last batch make money?" presumes a batch that ran and money that was
  counted. Tagged.

  "How would this game actually make money, a price, ads or in game buying?" is
  a planning question, and a founder who has sold nothing is exactly who should
  be asked it. Not tagged.

  "Do you know the lowest price you can accept and still make money?" is costing,
  answerable before a first sale. Not tagged.

  "Right now, is your focus mostly on getting more users, with earning money from
  them left as a problem for later?" is ABOUT not yet earning. Tagging it would
  withhold it from the only people it is for. Not tagged.

That is the fourth time keyword screening this bank would have been wrong in
both directions, so every code is listed and the upgrade reports what it could
not find rather than failing the release (see 8b63ca0f).

AND THIS CLASS IS NOT FINISHED BY SWEEPING, which is worth recording because
four rounds have now each found a few more. Re-running the same diagnosis after
tagging the first fifteen reshuffled the ranking and surfaced two further leaks
in the questions the founder actually received -- "When did you last chase an
unpaid fee?" among them. A sweep for the phrasings those two use returns 25
candidates of which 14 are plainly fine, because "your customers" is how the
bank addresses TARGET customers everywhere. So the remaining leaks are found by
running real diagnoses as pre-revenue founders and reading what they are asked,
not by another regex round.

NONE OF THE FIFTEEN IS ON THE IDEATION BANK, checked before writing: an ideation
founder is never trading, so a tagged question there would be unreachable rather
than withheld -- the trap e81c47a92f36 fell into with S0-SPF-008, and the one
test_no_ideation_question_needs_a_trading_business exists to catch.

Revision ID: f74b2e9c1a60
Revises: d6a93f15b802
Create Date: 2026-10-03 09:00:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import bindparam, text

revision = "f74b2e9c1a60"
down_revision = "d6a93f15b802"
branch_labels = None
depends_on = None

_REWORD: tuple[tuple[str, str, str], ...] = (
    (
        "IVA-061",
        "Do you fear negative reactions from investors who funded a specific "
        "direction you now want to change?",
        "Do you fear how a change of direction would land with anyone who "
        "backed this one -- an investor, family, a co-founder, or someone who "
        "vouched for you?",
    ),
)

#: Each presumes money has already changed hands. Read one at a time; the nine
#: that merely use the same words are deliberately absent, see the docstring.
_REQUIRES_TRADING: tuple[str, ...] = (
    "S0-EDU-301-2", "S0-MED-301-1", "S0-PRP-201-2", "S0-TRD-303-1",
    "S01-HRT-014", "S01-HRT-303-2", "S01-TRD-309-2", "S10-BPC-102-1",
    "S10-FNB-023", "S10-FND-005", "S10-HLT-001", "S10-HRT-015",
    "S10-HRT-303-2", "S10-LGL-022", "S10-TRD-303-2",
    # Found on the SECOND run of the same diagnosis, after the first fifteen
    # were tagged and the ranking reshuffled what she was asked. That is the
    # method this class now needs: each real diagnosis surfaces the leaks a
    # keyword round leaves behind.
    "S01-EDU-301-2",   # "When did you last chase an unpaid fee?"
    "S01-LOG-309-2",   # "Where would someone read your customers' payment
                       #  history?" -- the identical twin of S01-TRD-309-2,
                       #  which a6f3d2c81b47 already tagged. An inconsistency
                       #  rather than a judgement call.
)

_IDEATION = "Stage 0"


def _apply(pairs: tuple[tuple[str, str, str], ...]) -> None:
    """Rewrite each question, skipping any whose text has moved on.

    Tolerant for the reason 8b63ca0f gives: raising inside `alembic upgrade
    head` stops the whole release, and a question somebody else has already
    reworded should keep their wording rather than mine.
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
            "with either their expected text or their rewording. That is the "
            f"wrong catalogue, not drift. Left alone: {left_alone}"
        )

    print(
        f"{revision}: reworded {applied}, already done {already_done}, "
        f"left alone {len(left_alone)}"
        + (f" -- {'; '.join(left_alone)}" if left_alone else "")
    )


def _set_trading(codes: tuple[str, ...], value: bool) -> None:
    """Flip `requires_trading`, skipping codes this catalogue does not have.

    Also refuses to strand a question on the ideation bank, where no founder is
    ever trading: tagging one there makes it unreachable instead of withheld.
    """
    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT question_code, primary_stage_group FROM questions "
            "WHERE question_code = ANY(:codes)"
        ),
        {"codes": list(codes)},
    ).all()
    present = {r[0] for r in rows}
    missing = sorted(set(codes) - present)

    if not present:
        raise RuntimeError(
            f"None of the {len(codes)} questions {revision} names are in this "
            "catalogue. That is the wrong database, not drift."
        )

    if value:
        stranded = sorted(r[0] for r in rows if r[1] == _IDEATION)
        if stranded:
            raise RuntimeError(
                f"{stranded} would be tagged on the {_IDEATION!r} bank, where no "
                "founder is ever trading, so they would become unreachable "
                "rather than withheld. Move them to a later bank first, the way "
                "e81c47a92f36 moved S0-SPF-008."
            )

    bind.execute(
        text(
            "UPDATE questions SET requires_trading = :value, updated_at = now() "
            "WHERE question_code = ANY(:codes)"
        ),
        {"value": value, "codes": sorted(present)},
    )
    print(
        f"{revision}: requires_trading={value} on {len(present)} of {len(codes)}"
        + (f"; not in this catalogue: {', '.join(missing)}" if missing else "")
    )


def upgrade() -> None:
    _apply(_REWORD)
    _set_trading(_REQUIRES_TRADING, True)


def downgrade() -> None:
    _set_trading(_REQUIRES_TRADING, False)
    _apply(tuple((code, new, old) for code, old, new in _REWORD))
