"""Stop industry questions presuming one kind of business within the industry.

A founder picks their industry at onboarding and the diagnosis draws on that
industry's bank. But an industry is not a business model, and 64 of those
questions were written as though it were. Measured on a real diagnosis: a founder
selling booking software to physiotherapy clinics was asked "Out of 100 patients,
how many use you a second time?" and "How much of your week goes on clinical
work?". He has no patients and is not a clinician. A founder selling banana chips
online was asked what happened to "covers and waste" the last time she "cut the
menu".

THE TEST EACH QUESTION WAS READ AGAINST. A question is wrong when it asks the
founder about operations they do not run or people they do not have -- your
kitchen, your drivers, your week on clinical work. It is right when it names the
industry's own reality -- who ultimately pays, what the regulator requires, who
the end beneficiary is, who you are selling to -- because that is as true for a
supplier to the industry as for an operator in it. "Who actually hands over the
money, the patient, an employer, an insurer or the government?" is a good
question for the software seller, and is left alone.

WHAT THE MEASURE DOES NOT CHANGE. Every rewording keeps what the question takes:
repeat usage stays repeat usage, cost-to-serve stays cost-to-serve, range
discipline stays range discipline. Only the noun moves. Nothing is added,
withheld, retagged or rescoped, and no row changes pillar, stage group, team
size or industry -- so coverage after this migration is identical to coverage
before it, question for question.

THE OTHER 64 OF THE 128 FLAGGED, AND WHY THEY ARE NOT HERE.

  37 need no change. The flagged word named the industry's reality, not a
  defect, and three were plain false positives on "covers" -- "covers every
  legal duty", "what each session covers", "insurance still covers".

  27 cannot be reworded at all. The subject really is a kitchen, a fleet, a
  clinical rota or a second location, and no neutral noun keeps the question
  meaningful: "Is there a maintenance calendar for your fleet?" cannot be
  rewritten for a founder with no vehicles, only withheld from them. Those need
  a scoping axis that does not exist yet -- owns production, owns a fleet or
  premises, operates more than one location -- which is the same shape as
  `min_team_size` and `requires_trading` and is separate work.

EVERY OLD TEXT IS SPELLED OUT IN FULL AND MATCHED EXACTLY, and the upgrade
counts the rows it changed and raises if the count is wrong. A rewording that
silently matched nothing is the one failure mode here: it leaves the bad text
live while the migration reports success. Matching on a pattern instead would
have made that failure invisible, and keyword matching over this bank has
already been wrong in both directions twice (see d4a1f8c62b73, a6f3d2c81b47).

The downgrade restores every original exactly, for the same reason and with the
same check.

See docs/drafts/industry-question-rewording.md for the review these pairs came
from, including the two buckets left alone.

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

#: (question_code, text as it is now, text it becomes). Grouped by industry,
#: in the order the review document lists them.
_REWORD: tuple[tuple[str, str, str], ...] = (

    # --- Delivery --------------------------------------------------
    (
        'S0-DLV-304-1',
        'Who is responsible for how well your riders do their job?',
        'Who is responsible for how well your deliveries actually get done?',
    ),
    (
        'S01-DLV-006',
        'Is knowledge of your routes written down, or is it only in your '
        "drivers' heads?",
        'Is knowledge of your routes written down, or is it only in '
        "people's heads?",
    ),

    # --- E-commerce ------------------------------------------------
    (
        'S0-ECM-006',
        'If your store went live today, how would the very first stranger '
        'find it?',
        'If you went live today, how would the very first stranger find you?',
    ),
    (
        'S0-ECM-009',
        'Do you have any idea what it costs to get one person to visit your '
        'store?',
        'Do you have any idea what it costs to get one new person to look '
        'at what you sell?',
    ),

    # --- Education -------------------------------------------------
    (
        'S0-EDU-304-1',
        'Who is responsible for whether students finish the course?',
        'Who is responsible for whether learners finish what they start?',
    ),
    (
        'S10-EDU-307-1',
        'Last year, did your work improve the institute, or did it only '
        'fill batches with students?',
        'Last year, did your work make the business stronger, or did it '
        'only fill more seats?',
    ),

    # --- Food & Beverage -------------------------------------------
    (
        'S0-FNB-102-1',
        'How do you decide whether to add a dish to your menu?',
        'How do you decide whether to add a new item to what you sell?',
    ),
    (
        'S0-FNB-102-2',
        'Have you ever removed a dish, and what made you decide?',
        'Have you ever removed something you sell, and what made you decide?',
    ),
    (
        'S0-FNB-104-1',
        'When a dish goes out wrong, who owns putting it right?',
        'When an order goes out wrong, who owns putting it right?',
    ),
    (
        'S0-FNB-301-1',
        'Do you know what your most popular dish costs you to make?',
        'Do you know what your most popular item costs you to make?',
    ),
    (
        'S0-FNB-303-2',
        'Could someone else cook your signature dish the same way?',
        'Could someone else make your signature product the same way?',
    ),
    (
        'S0-FNB-306-2',
        'Where did you find the last person you hired for the kitchen or '
        'for serving customers?',
        'Where did you find the last person you hired to make or to serve '
        'what you sell?',
    ),
    (
        'S01-FNB-006',
        'Is there a written recipe card in the kitchen, or is it from memory?',
        'Is there a written recipe or spec for what you make, or is it from '
        'memory?',
    ),
    (
        'S01-FNB-019',
        'When did you last recalculate what a dish costs you to make?',
        'When did you last recalculate what an item costs you to make?',
    ),
    (
        'S01-FNB-102-1',
        'Which of your dishes sell least, and what do they cost you to keep '
        'on?',
        'Which of your items sell least, and what do they cost you to keep '
        'on?',
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
        'S01-FNB-110-1',
        'When something goes wrong in the kitchen, is the cause written down?',
        'When something goes wrong in production, is the cause written down?',
    ),
    (
        'S01-FNB-110-2',
        'What does a new kitchen hire have to learn that nobody has written?',
        'What does someone new on the food side have to learn that nobody '
        'has written down?',
    ),
    (
        'S01-FNB-301-2',
        'Which dish on your menu makes you the least money?',
        'Which item in your range makes you the least money?',
    ),
    (
        'S01-FNB-303-2',
        'What happens to the menu when you are away for a week?',
        'What happens to your range when you are away for a week?',
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
        'S10-FNB-020',
        'How many items are on your menu now, and how many two years ago?',
        'How many items do you sell now, and how many two years ago?',
    ),
    (
        'S10-FNB-023',
        'Do you know which dishes actually make money and which lose it?',
        'Do you know which items actually make money and which lose it?',
    ),
    (
        'S10-FNB-101-1',
        'How do you measure variance between what the spec says and what '
        'leaves the kitchen?',
        'How do you measure the gap between what the spec says and what '
        'actually ships?',
    ),
    (
        'S10-FNB-102-1',
        'What is your rule for adding a new item to the menu?',
        'What is your rule for adding a new item to your range?',
    ),
    (
        'S10-FNB-102-2',
        'What happened to covers and waste the last time you cut the menu?',
        'What happened to sales and waste the last time you cut your range?',
    ),

    # --- Healthcare ------------------------------------------------
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
    (
        'S0-HLT-302-1',
        'How much of your week goes on clinical work, and how much on '
        'running the company?',
        'How much of your week goes on delivering the service itself, and '
        'how much on running the company?',
    ),
    (
        'S01-HLT-006',
        'Out of 100 patients, how many use you a second time?',
        'Out of 100 customers, how many use you a second time?',
    ),
    (
        'S01-HLT-007',
        'Does a patient hear from you after the first consult or test?',
        'Does a customer hear from you after the first time they use you?',
    ),
    (
        'S01-HLT-008',
        'Is there any reason a patient would need you again?',
        'Is there any reason a customer would need you again?',
    ),
    (
        'S01-HLT-009',
        'Do patients go back to their usual doctor or lab after trying you?',
        'Do customers go back to what they used before after trying you?',
    ),
    (
        'S01-HLT-010',
        'Is your growth coming from new patients or returning ones?',
        'Is your growth coming from new customers or returning ones?',
    ),
    (
        'S01-HLT-011',
        'What stops you serving twice as many patients tomorrow?',
        'What stops you serving twice as many customers tomorrow?',
    ),
    (
        'S01-HLT-016',
        'What does it really cost you to serve one patient, counting every '
        'cost?',
        'What does it really cost you to serve one customer, counting every '
        'cost?',
    ),
    (
        'S10-HLT-002',
        'How many patients do you need in one area before a city pays for '
        'itself?',
        'How many customers do you need in one area before a city pays for '
        'itself?',
    ),
    (
        'S10-HLT-003',
        'Why does it cost more to serve a patient in a new city?',
        'Why does it cost more to serve a customer in a new city?',
    ),
    (
        'S10-HLT-015',
        'What share of your patients come through a few partner '
        'organisations, such as hospitals, insurers or employers?',
        'What share of your customers come through a few partner '
        'organisations, such as hospitals, insurers or employers?',
    ),
    (
        'S10-HLT-302-2',
        'How much of your week could a non-clinician handle?',
        'How much of your week could somebody without your specialist '
        'training handle?',
    ),

    # --- Retail ----------------------------------------------------
    (
        'S0-RTL-307-1',
        'Where do you want your shop to be in three years?',
        'Where do you want the business to be in three years?',
    ),
    (
        'S01-RTL-008',
        "Can you see a customer's full history across your shop and online "
        'in one place, or is it kept in two separate places?',
        "Can you see a customer's full history across everywhere you sell "
        'in one place, or is it kept in separate places?',
    ),
    (
        'S10-RTL-303-2',
        'What knowledge about running your shop is still only in your head?',
        'What knowledge about running the business is still only in your '
        'head?',
    ),
    (
        'S10-RTL-304-1',
        'Which job in your shop still has no one clearly responsible for it?',
        'Which job in the business still has no one clearly responsible for '
        'it?',
    ),
    (
        'S10-RTL-304-2',
        "Do your shop's standards change depending on which staff are "
        'working?',
        'Do your standards change depending on which staff are working?',
    ),

    # --- Trading / Import-Export -----------------------------------
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

    # --- Travel & Hospitality --------------------------------------
    (
        'S0-TRV-005',
        'How will you get through the quiet season when few guests come?',
        'How will you get through the quiet season when few customers come?',
    ),
    (
        'S0-TRV-303-2',
        'If you were not there, could someone else welcome your guests the '
        'way you do?',
        'If you were not there, could someone else look after your '
        'customers the way you do?',
    ),
    (
        'S01-TRV-004',
        'Do you have contact details for guests who stayed with you?',
        'Do you have contact details for the customers you have served?',
    ),
    (
        'S01-TRV-010',
        'Do you ask happy guests to leave a review?',
        'Do you ask happy customers to leave a review?',
    ),
    (
        'S01-TRV-012',
        'Is there anything written down about how guests should be looked '
        'after?',
        'Is there anything written down about how customers should be '
        'looked after?',
    ),
    (
        'S01-TRV-016',
        'Do you have a clear cancellation policy guests agree to?',
        'Do you have a clear cancellation policy customers agree to?',
    ),
    (
        'S01-TRV-302-1',
        'What do guests complain about most?',
        'What do customers complain about most?',
    ),
    (
        'S10-TRV-013',
        'How many months could you cover costs with no guests at all?',
        'How many months could you cover costs with no customers at all?',
    ),
    (
        'S10-TRV-015',
        'Where do most of your guests come from, and is it one place?',
        'Where do most of your customers come from, and is it one place?',
    ),
    (
        'S10-TRV-305-1',
        'Which decisions about guests still have to wait for you?',
        'Which decisions about customers still have to wait for you?',
    ),

    # --- Consumer Electronics --------------------------------------
    (
        'S10-CEL-005',
        'How do you usually find out about a quality problem, from your '
        'factory or from customers?',
        'How do you usually find out about a quality problem, from your own '
        'checks or from customers?',
    ),
    (
        'S10-CEL-020',
        'If your factory stopped tomorrow, how long before you could '
        'produce anywhere else?',
        'If the place that makes your product stopped tomorrow, how long '
        'before you could produce anywhere else?',
    ),

    # --- Fashion ---------------------------------------------------
    (
        'S10-FSH-020',
        'If a buyer asked about your factory labour conditions, could you '
        'answer?',
        'If a buyer asked about labour conditions where your product is '
        'made, could you answer?',
    ),

)


def _apply(pairs: tuple[tuple[str, str, str], ...]) -> None:
    """Rewrite each question, and raise unless every row was found as expected.

    One statement per pair, matching on BOTH the code and the full current text.
    The code alone would be enough to find the row; the text is in the WHERE
    clause so that a row somebody else has already edited is left alone and
    reported, rather than silently overwritten with a rewording of text that no
    longer exists.
    """
    stmt = text(
        """
        UPDATE questions SET question_text = :new, updated_at = now()
        WHERE question_code = :code AND question_text = :old
        """
    ).bindparams(bindparam("new"), bindparam("code"), bindparam("old"))

    missed = []
    for code, old, new in pairs:
        result = op.get_bind().execute(stmt, {"code": code, "old": old, "new": new})
        if result.rowcount != 1:
            missed.append(f"{code} (matched {result.rowcount} rows)")

    if missed:
        raise RuntimeError(
            "Question text has moved since this migration was written, so these "
            "rewordings matched nothing and the originals are still live: "
            + "; ".join(missed)
            + ". Re-read the current text and update the pairs in "
            "a3f7b21c6d84 -- do not loosen the match."
        )


def upgrade() -> None:
    _apply(_REWORD)


def downgrade() -> None:
    _apply(tuple((code, new, old) for code, old, new in _REWORD))
