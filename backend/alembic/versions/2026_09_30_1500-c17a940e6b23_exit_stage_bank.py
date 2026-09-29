"""Give Exit its own questions, and its own bank to keep them in.

A founder who picks "Exit -- preparing to hand it on or sell" gets 2,414
questions and not one of them is about exiting. Searched the whole bank before
writing any of this: nothing mentions succession, handing over, selling the
business, a buyer, or what happens afterwards. They get a solid general
check-up and nothing about their actual situation.

WHY A FOURTH BANK. These cannot live in `Stage 1->10+`, which Growth,
Expansion and Maturity also draw from -- a founder scaling up would be asked
what a buyer would discount them for. So `questions.primary_stage_group` gains
a fourth value and `stage_groups_for` gives an Exit founder BOTH groups: the
general bank they still need, plus this one.

An unknown stage is the one place that does not get it. `stage_groups_for`
fails open to every group when it cannot place a founder, and that is right for
the three general banks -- returning nothing would dead-end the assessment. It
is wrong here: "What would you have to fix before letting a buyer watch a
normal week?" put to someone whose stage we simply failed to read is worse than
one question fewer, and three banks is not a dead end.

200 questions, 20 in each of ten topics, so two founders at Exit do not draw an
identical diagnosis. Written to cover all six pillars -- the first seven topics
reached five, and Customer Definition was added to bring in Market Clarity so
an Exit founder's report does not go quiet on a whole section.

Each question carries the flags the existing gates read, so this needs no
second pass to work out who may be asked what: 157 are answerable by a founder
working alone, 43 need other people, and 109 need a first sale to have
happened. Categories were chosen so none of them is one Exit withholds (see
EXIT_WITHHELD_CATEGORIES) and so each sits in the pillar the rest of the
catalogue already files it under.

The source is docs/drafts/exit-stage-questions.md, which is the reviewable
version. This file is generated from it; edit the draft and regenerate rather
than editing the tuples below by hand.

Revision ID: c17a940e6b23
Revises: f0b82e4d5a19
Create Date: 2026-09-30 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c17a940e6b23"
down_revision: Union[str, Sequence[str], None] = "f0b82e4d5a19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUP = "Exit"
_STAGE_GROUP_CHECK = "questions_primary_stage_group_check"
_GROUPS = ("Stage 0", "Stage 0\u21921", "Stage 1\u219210+", _GROUP)

#: One problem per topic, each carrying the dimension it assesses so the
#: report can name what was covered. `severity_min`/`max` match the existing
#: founder-dependency problems, which are the closest neighbours in weight.
_BANK: tuple[dict, ...] = (
    {
        "problem_code": 'EXT-001',
        "problem_name": 'The Business Cannot Run Without the Founder',
        "category": 'Founder Psychology',
        "pillar_id": 1,
        "dimension_code": 'founder_dependency',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-001-01', 'If you stopped working tomorrow, how long would the business keep running normally?', None, False),
            ('EXIT-001-02', 'What is the first thing that would break if you were away for a month?', None, False),
            ('EXIT-001-03', 'Which customers would ask for you by name if you were not there?', None, True),
            ('EXIT-001-04', 'Is there anything only you know how to do? Name one.', None, False),
            ('EXIT-001-05', 'When did you last take two full weeks off without being contacted?', None, False),
            ('EXIT-001-06', 'If a buyer asked you to stay on for a year, would the business need that?', None, False),
            ('EXIT-001-07', 'How many decisions in a normal week wait for you?', None, False),
            ('EXIT-001-08', 'Do suppliers deal with you personally, or with the business?', None, True),
            ('EXIT-001-09', "Whose phone number do customers have — yours, or the company's?", None, True),
            ('EXIT-001-10', 'What part of the work would you struggle to explain to someone taking over?', None, False),
            ('EXIT-001-11', 'Have you ever tried handing over a part of your job? What happened?', '2_5', False),
            ('EXIT-001-12', 'Is there a written list of what you actually do in a week?', None, False),
            ('EXIT-001-13', 'Would the business lose money in the first month without you, and how much?', None, True),
            ('EXIT-001-14', 'Do you believe nobody else could run this as well as you?', None, False),
            ('EXIT-001-15', 'What do you still do yourself that somebody else could have been doing for a year?', None, False),
            ('EXIT-001-16', 'If you were ill for three months, who would open the business each day?', '2_5', False),
            ('EXIT-001-17', 'Are there passwords, accounts or keys that only you hold?', None, False),
            ('EXIT-001-18', 'Does the business have relationships, or do you have them?', None, True),
            ('EXIT-001-19', 'What would a new owner have to learn from you that is written down nowhere?', None, False),
            ('EXIT-001-20', 'Have you been putting off stepping back because it feels like losing control?', None, False),
        ),
    },
    {
        "problem_code": 'EXT-002',
        "problem_name": 'Income Sits With Too Few Customers to Survive a Handover',
        "category": 'Sales & Revenue',
        "pillar_id": 3,
        "dimension_code": 'revenue_concentration',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-002-01', 'What share of your money comes from your biggest customer?', None, True),
            ('EXIT-002-02', 'If your three biggest customers left, would the business survive?', None, True),
            ('EXIT-002-03', 'How long has your biggest customer been with you?', None, True),
            ('EXIT-002-04', 'Is there a signed agreement with your biggest customers, or is it based on trust?', None, True),
            ('EXIT-002-05', 'Would your biggest customer stay if you sold the business?', None, True),
            ('EXIT-002-06', 'Who at your biggest customer actually knows the company, besides you?', None, True),
            ('EXIT-002-07', 'When did you last win a customer as big as your biggest one?', None, True),
            ('EXIT-002-08', 'Do you know which customers make you money and which ones cost you?', None, True),
            ('EXIT-002-09', 'Has a big customer ever left suddenly? What happened to the money that month?', None, True),
            ('EXIT-002-10', 'How many customers gave you money in the last three months?', None, True),
            ('EXIT-002-11', 'Is your income steady each month, or does it jump around?', None, True),
            ('EXIT-002-12', 'Does one product or service bring in most of your money?', None, True),
            ('EXIT-002-13', 'If your biggest customer asked for a big discount tomorrow, could you say no?', None, True),
            ('EXIT-002-14', 'Are you depending on one supplier as much as one customer?', None, True),
            ('EXIT-002-15', 'What would you tell a buyer worried that your income sits with too few names?', None, True),
            ('EXIT-002-16', 'Have you tried to spread your income across more customers? What stopped you?', None, True),
            ('EXIT-002-17', 'Does any customer owe you money that is badly overdue right now?', None, True),
            ('EXIT-002-18', 'Do repeat customers come back on their own, or because you chase them?', None, True),
            ('EXIT-002-19', 'Which part of your income would you be most nervous showing a buyer?', None, True),
            ('EXIT-002-20', "Is any of your income tied to one person's contacts rather than the business?", None, True),
        ),
    },
    {
        "problem_code": 'EXT-003',
        "problem_name": 'What the Founder Knows Is Written Down Nowhere',
        "category": 'Strategy & Planning',
        "pillar_id": 6,
        "dimension_code": 'institutional_memory',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-003-01', 'If someone took over on Monday, what would they read first?', None, False),
            ('EXIT-003-02', 'Is there any written record of how the main work gets done?', None, False),
            ('EXIT-003-03', 'Where are your customer details kept — a system, a notebook, or your phone?', None, True),
            ('EXIT-003-04', 'Could someone else find a two-year-old customer agreement today?', None, True),
            ('EXIT-003-05', 'Is there a reason written down for the prices you charge?', None, False),
            ('EXIT-003-06', 'What do you know about your customers that exists only in your head?', None, True),
            ('EXIT-003-07', 'Have you ever lost something important because it was never written down?', None, False),
            ('EXIT-003-08', 'Are your supplier terms recorded anywhere, or agreed by conversation?', None, True),
            ('EXIT-003-09', 'If a key person left today, what would leave with them?', '2_5', False),
            ('EXIT-003-10', 'Is there a written list of who your regular suppliers are and what you pay them?', None, True),
            ('EXIT-003-11', 'When something goes wrong, is there a written way of handling it?', None, False),
            ('EXIT-003-12', 'Could a new owner see why you dropped a product or a customer in the past?', None, True),
            ('EXIT-003-13', 'Do you keep notes from important meetings, or rely on memory?', None, False),
            ('EXIT-003-14', 'Is anything written down about what did not work and why?', None, False),
            ('EXIT-003-15', 'Where would a buyer look to understand how this business actually makes money?', None, True),
            ('EXIT-003-16', 'Is there a handover note for any role in the business?', '2_5', False),
            ('EXIT-003-17', 'How long would it take you to gather three years of records if asked tomorrow?', None, True),
            ('EXIT-003-18', 'Do you avoid writing things down because it feels slower than just doing it?', None, False),
            ('EXIT-003-19', 'Is there a single place where the important documents live?', None, False),
            ('EXIT-003-20', 'What would you have to sit and explain for a week before you could walk away?', None, False),
        ),
    },
    {
        "problem_code": 'EXT-004',
        "problem_name": 'Nobody Is Ready to Take Over What the Founder Does',
        "category": 'Team & Leadership',
        "pillar_id": 5,
        "dimension_code": 'team_structure_role_clarity',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-004-01', 'Is there anyone who could run this business day to day without you?', '2_5', False),
            ('EXIT-004-02', 'Does your team know you are thinking about handing over or selling?', '2_5', False),
            ('EXIT-004-03', 'Who would you want to stay if the business changed hands?', '2_5', False),
            ('EXIT-004-04', 'Would your best people stay for a new owner, honestly?', '2_5', False),
            ('EXIT-004-05', "Is each person's job written down anywhere?", '2_5', False),
            ('EXIT-004-06', 'If you promoted someone into your role today, what would they struggle with?', '2_5', False),
            ('EXIT-004-07', 'Has anyone been told they might take over part of your work?', '2_5', False),
            ('EXIT-004-08', 'Are people paid in a way a new owner would find normal?', '6_10', False),
            ('EXIT-004-09', 'Do any of your team have agreements in writing?', '2_5', False),
            ('EXIT-004-10', 'Is anyone in the team related to you or a close friend?', '2_5', False),
            ('EXIT-004-11', 'Who trains a new person today — you, or somebody else?', '2_5', False),
            ('EXIT-004-12', 'Has anyone on your team ever run a part of the business while you were away?', '2_5', False),
            ('EXIT-004-13', 'Does anyone besides you know the full picture of how the business runs?', '2_5', False),
            ('EXIT-004-14', 'Would the team keep working normally in the week after you announced a sale?', '2_5', False),
            ('EXIT-004-15', 'Is there someone you quietly worry the business could not manage without?', '2_5', False),
            ('EXIT-004-16', 'Have you promised anyone a share of the business, even verbally?', '2_5', False),
            ('EXIT-004-17', 'Do people come to you for things their own job should cover?', '2_5', False),
            ('EXIT-004-18', 'Is there a second person who can do each important job?', '6_10', False),
            ('EXIT-004-19', 'What would you tell your team the day the sale was agreed?', '2_5', False),
            ('EXIT-004-20', 'Have you avoided talking about the future with your team because it feels awkward?', '2_5', False),
        ),
    },
    {
        "problem_code": 'EXT-005',
        "problem_name": 'The Books Would Not Survive Being Looked Through',
        "category": 'Business Model Design',
        "pillar_id": 3,
        "dimension_code": 'revenue_model_clarity',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-005-01', 'Could you show someone your last two years of numbers this week?', None, True),
            ('EXIT-005-02', 'Are your business money and your personal money kept separate?', None, True),
            ('EXIT-005-03', 'Does anyone besides you check the numbers?', None, True),
            ('EXIT-005-04', 'Do you know what you actually keep from every hundred rupees that comes in?', None, True),
            ('EXIT-005-05', 'Are there costs the business pays that are really personal?', None, True),
            ('EXIT-005-06', 'Is anything paid or received in cash that would be hard to show?', None, True),
            ('EXIT-005-07', 'Would your numbers match your bank statements if someone compared them?', None, True),
            ('EXIT-005-08', 'Is your tax filing up to date?', None, True),
            ('EXIT-005-09', 'Do you know which of your products or services makes the most money?', None, True),
            ('EXIT-005-10', 'Has anyone outside the business ever looked at your accounts?', None, True),
            ('EXIT-005-11', 'Is money owed to you tracked anywhere, or do you remember it?', None, True),
            ('EXIT-005-12', 'Do you have loans or dues a new owner would take on?', None, True),
            ('EXIT-005-13', 'Are your prices written down, or agreed customer by customer?', None, False),
            ('EXIT-005-14', 'Could you explain in one minute how this business makes money?', None, False),
            ('EXIT-005-15', 'Has your way of charging changed in the last two years, and why?', None, True),
            ('EXIT-005-16', 'Is any income one-off rather than the kind that comes back every month?', None, True),
            ('EXIT-005-17', 'What would an accountant find messy if they opened your books tomorrow?', None, True),
            ('EXIT-005-18', 'Are there agreements with customers or suppliers that end when you leave?', None, True),
            ('EXIT-005-19', 'Do you avoid looking at the numbers closely because you expect bad news?', None, True),
            ('EXIT-005-20', 'Which number would you least like a buyer to ask about?', None, True),
        ),
    },
    {
        "problem_code": 'EXT-006',
        "problem_name": "Too Much Still Needs the Founder's Approval",
        "category": 'Team & Leadership',
        "pillar_id": 5,
        "dimension_code": 'decision_rights',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-006-01', 'What can nobody else in the business approve without you?', '2_5', False),
            ('EXIT-006-02', 'Is there a written limit on what others can spend?', '2_5', False),
            ('EXIT-006-03', 'Can anyone else agree a price with a customer?', '2_5', True),
            ('EXIT-006-04', 'Who can hire someone without asking you?', '6_10', False),
            ('EXIT-006-05', 'Can anyone else sign an agreement for the business?', '2_5', False),
            ('EXIT-006-06', 'How often does work stop while people wait for your answer?', '2_5', False),
            ('EXIT-006-07', 'Is there a written rule for giving a refund or a discount?', None, True),
            ('EXIT-006-08', 'Could someone else pay a supplier while you were away?', '2_5', True),
            ('EXIT-006-09', 'Do you check work that does not really need checking?', '2_5', False),
            ('EXIT-006-10', 'Which decision did you make last week that somebody else should have made?', '2_5', False),
            ('EXIT-006-11', 'Are bank accounts in a position where only you can move money?', None, True),
            ('EXIT-006-12', 'Has anyone ever made a decision you later reversed? What did that teach them?', '2_5', False),
            ('EXIT-006-13', 'If a customer complained today, who could settle it without you?', '2_5', True),
            ('EXIT-006-14', 'Do you hold on to approvals because letting go feels risky?', '2_5', False),
            ('EXIT-006-15', 'Is it clear who decides what, or does it get worked out each time?', '2_5', False),
            ('EXIT-006-16', 'What is the biggest amount somebody else can commit the business to?', '2_5', False),
            ('EXIT-006-17', 'Could the business buy stock or materials without you this week?', '2_5', True),
            ('EXIT-006-18', 'Are there decisions you would not hand over even to a new owner?', None, False),
            ('EXIT-006-19', 'Do people ask your permission for things you would rather they just did?', '2_5', False),
            ('EXIT-006-20', 'If you gave someone your approvals for a month, what would you worry about most?', '2_5', False),
        ),
    },
    {
        "problem_code": 'EXT-007',
        "problem_name": 'The Work Holds Up Only Because the Founder Rescues It',
        "category": 'Product',
        "pillar_id": 4,
        "dimension_code": 'reliability_real_world',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-007-01', 'How often do you personally step in to fix something for a customer?', None, True),
            ('EXIT-007-02', 'What goes wrong most often, and has it been fixed properly or worked around?', None, True),
            ('EXIT-007-03', 'Would a new owner find the same problem coming back every month?', None, True),
            ('EXIT-007-04', 'Is there a written standard for what a good job looks like?', None, False),
            ('EXIT-007-05', 'Do customers ever get a different experience depending on who serves them?', '2_5', True),
            ('EXIT-007-06', 'How do you know when something has gone wrong — do you find out, or do they tell you?', None, True),
            ('EXIT-007-07', 'Is there anything held together by your own effort rather than a proper fix?', None, False),
            ('EXIT-007-08', 'What would break first if the work doubled?', None, True),
            ('EXIT-007-09', 'Do you keep any record of complaints and what caused them?', None, True),
            ('EXIT-007-10', 'Is there equipment or software that is overdue for replacing?', None, False),
            ('EXIT-007-11', 'Has a customer ever left because of a problem that kept repeating?', None, True),
            ('EXIT-007-12', 'Could someone else follow your process and get the same result?', None, False),
            ('EXIT-007-13', 'What do you personally check before work goes out?', None, True),
            ('EXIT-007-14', "Is anything important running on one person's laptop or phone?", None, False),
            ('EXIT-007-15', 'How long does it take to get back to normal after something goes wrong?', None, True),
            ('EXIT-007-16', 'Do you depend on one supplier who has let you down before?', None, True),
            ('EXIT-007-17', 'Is there a backup if your main tool or machine stopped today?', None, False),
            ('EXIT-007-18', 'What would you fix before letting a buyer watch a normal week?', None, True),
            ('EXIT-007-19', 'Do you assume problems are one-offs rather than looking for the pattern?', None, False),
            ('EXIT-007-20', 'Which part of the work would you not want a new owner to see on a bad day?', None, True),
        ),
    },
    {
        "problem_code": 'EXT-008',
        "problem_name": 'No Real Plan for Life After Handing Over',
        "category": 'Business Planning',
        "pillar_id": 6,
        "dimension_code": 'plan_to_vision_alignment',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-008-01', 'What do you actually want to do after you hand this over?', None, False),
            ('EXIT-008-02', 'Is there a date in your head, or is it still "sometime"?', None, False),
            ('EXIT-008-03', 'Have you told anyone outside the business that you are thinking about this?', None, False),
            ('EXIT-008-04', 'What would have to be true before you felt ready to let go?', None, False),
            ('EXIT-008-05', 'Is there a number that would be enough for you?', None, False),
            ('EXIT-008-06', 'Are you making decisions now that only pay off in five years?', None, False),
            ('EXIT-008-07', 'Would you stay on for a year if a buyer asked, or is leaving the point?', None, False),
            ('EXIT-008-08', 'What matters more to you — the price, or what happens to the people here?', None, False),
            ('EXIT-008-09', 'Does your family know what you are planning?', None, False),
            ('EXIT-008-10', 'Have you spoken to anyone who has sold a business before?', None, False),
            ('EXIT-008-11', 'What are you still spending on that a buyer would stop tomorrow?', None, True),
            ('EXIT-008-12', 'If a fair offer came next month, would you be ready or would you ask for time?', None, False),
            ('EXIT-008-13', 'Is anything in your plan for this year there only because you have always done it?', None, False),
            ('EXIT-008-14', 'What would make you call the whole thing off?', None, False),
            ('EXIT-008-15', 'Are you holding back from a big decision because you might be leaving?', None, False),
            ('EXIT-008-16', 'Does the way you run the business today match someone who is preparing to go?', None, False),
            ('EXIT-008-17', 'Is there work you keep starting because stopping would feel like giving up?', None, False),
            ('EXIT-008-18', 'What do you want this business to be known for after you are gone?', None, False),
            ('EXIT-008-19', 'Have you written any of this plan down, or does it live in your head?', None, False),
            ('EXIT-008-20', 'If you never sold and ran this for ten more years, would that be a failure?', None, False),
        ),
    },
    {
        "problem_code": 'EXT-009',
        "problem_name": 'Demand Depends on the Founder Bringing It In',
        "category": 'Sales & Revenue',
        "pillar_id": 3,
        "dimension_code": 'demand_reality',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-009-01', 'Is the work coming in growing, steady, or slowly dropping?', None, True),
            ('EXIT-009-02', 'Where does most of your new business actually come from?', None, True),
            ('EXIT-009-03', 'If you stopped asking people for work, would enquiries keep arriving?', None, True),
            ('EXIT-009-04', 'Do customers come because of you, or because of what the business does?', None, True),
            ('EXIT-009-05', 'How many enquiries did you get in the last three months?', None, True),
            ('EXIT-009-06', 'Are most of your referrals from your own contacts?', None, True),
            ('EXIT-009-07', 'Is your work seasonal, and does a buyer need to know that?', None, True),
            ('EXIT-009-08', 'When did you last have to chase work rather than turn it away?', None, True),
            ('EXIT-009-09', 'Could you say roughly what next quarter will bring in?', None, True),
            ('EXIT-009-10', 'Does any of your demand depend on one rule, licence or contract staying in place?', None, True),
            ('EXIT-009-11', 'Has a competitor appeared in the last two years? What changed?', None, True),
            ('EXIT-009-12', 'Do customers come back on their own, or only when you remind them?', None, True),
            ('EXIT-009-13', "What share of this year's work came from customers you already had?", None, True),
            ('EXIT-009-14', 'If a buyer watched your enquiries for a month, what would they see?', None, True),
            ('EXIT-009-15', 'Is demand tied to something that might pass, like a trend or a shortage?', None, True),
            ('EXIT-009-16', 'Do you have work booked beyond the next month?', None, True),
            ('EXIT-009-17', 'Has demand ever dropped suddenly? What caused it?', None, True),
            ('EXIT-009-18', 'Are you turning work away, and why?', None, True),
            ('EXIT-009-19', 'Would the phone still ring if you took your name off everything?', None, True),
            ('EXIT-009-20', 'What would worry you most about demand if you were the one buying?', None, True),
        ),
    },
    {
        "problem_code": 'EXT-010',
        "problem_name": 'A Buyer Could Not Say Who the Customers Are',
        "category": 'Target Customer & ICP',
        "pillar_id": 2,
        "dimension_code": 'customer_definition',
        "subcategory": 'Handover Readiness',
        "questions": (
            ('EXIT-010-01', 'Describe your typical customer in one sentence.', None, False),
            ('EXIT-010-02', 'Are your customers mostly one kind of person or business, or all sorts?', None, True),
            ('EXIT-010-03', 'Who is your best customer, and what makes them the best?', None, True),
            ('EXIT-010-04', 'Is there a written list of who your customers are?', None, True),
            ('EXIT-010-05', 'Which customers would you not want to keep if you could choose?', None, True),
            ('EXIT-010-06', 'Do your customers know each other, or come from the same circles?', None, True),
            ('EXIT-010-07', 'How did you get your last five customers?', None, True),
            ('EXIT-010-08', 'Are your customers loyal to you personally or to what they get?', None, True),
            ('EXIT-010-09', 'What do your best customers have in common?', None, True),
            ('EXIT-010-10', 'Is there a type of customer you keep saying no to?', None, True),
            ('EXIT-010-11', 'Would a buyer recognise your customers as a group, or as a mixed bag?', None, True),
            ('EXIT-010-12', 'How long does a typical customer stay with you?', None, True),
            ('EXIT-010-13', 'Do you know why customers picked you over someone else?', None, True),
            ('EXIT-010-14', 'Is there a customer you would be embarrassed for a buyer to call?', None, True),
            ('EXIT-010-15', 'Which customers pay late, and do you keep taking their work?', None, True),
            ('EXIT-010-16', 'Are you serving a narrow group well, or a wide group roughly?', None, True),
            ('EXIT-010-17', 'Has the kind of customer you serve changed over the last few years?', None, True),
            ('EXIT-010-18', 'Could someone else describe your customer the same way you just did?', '2_5', False),
            ('EXIT-010-19', 'Do you know which customers would recommend you without being asked?', None, True),
            ('EXIT-010-20', 'If you had to drop half your customers, which half would go?', None, True),
        ),
    },
)


def upgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(_STAGE_GROUP_CHECK, "questions", type_="check")
    op.create_check_constraint(
        _STAGE_GROUP_CHECK, "questions",
        "primary_stage_group IN (" + ", ".join(f"'{g}'" for g in _GROUPS) + ")",
    )

    problems = added_q = 0
    for topic in _BANK:
        problem_id = bind.execute(
            sa.text(
                """
                INSERT INTO problems (problem_code, problem_name, category, layer,
                                      description, severity_min, severity_max,
                                      pillar_id, subcategory, dimension_code)
                VALUES (:code, :name, :category, 'internal', :description, 5, 9,
                        :pillar, :subcategory, :dimension)
                ON CONFLICT (problem_code) DO NOTHING
                RETURNING problem_id
                """
            ),
            {
                "code": topic["problem_code"], "name": topic["problem_name"],
                "category": topic["category"], "pillar": topic["pillar_id"],
                "subcategory": topic["subcategory"],
                "dimension": topic["dimension_code"],
                "description": (
                    f"{topic['problem_name']}. Assessed when a founder is "
                    "preparing to hand the business on or sell it."
                ),
            },
        ).scalar()
        if problem_id is None:                      # already present, re-run
            problem_id = bind.execute(
                sa.text("SELECT problem_id FROM problems WHERE problem_code = :c"),
                {"c": topic["problem_code"]},
            ).scalar_one()
        else:
            problems += 1

        cause_code = topic["problem_code"].replace("EXT-", "RC-EXT-")
        root_cause_id = bind.execute(
            sa.text(
                """
                INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name,
                                         root_cause_category, explanation,
                                         confidence_weight, layer)
                VALUES (:code, :pid, :name, 'Operational', :explanation, 0.70, 'internal')
                ON CONFLICT (root_cause_code) DO NOTHING
                RETURNING root_cause_id
                """
            ),
            {
                "code": cause_code, "pid": problem_id,
                "name": topic["problem_name"],
                "explanation": (
                    "The business has not been made independent of the founder "
                    "in this respect, which is what a handover exposes."
                ),
            },
        ).scalar()
        if root_cause_id is None:
            root_cause_id = bind.execute(
                sa.text("SELECT root_cause_id FROM root_causes WHERE root_cause_code = :c"),
                {"c": cause_code},
            ).scalar_one()

        for code, text, team, trading in topic["questions"]:
            added_q += bind.execute(
                sa.text(
                    """
                    INSERT INTO questions (question_code, category, question_text,
                                           problem_id, root_cause_id, question_type,
                                           difficulty_level, priority,
                                           primary_stage_group, min_team_size,
                                           requires_trading)
                    VALUES (:code, :category, :text, :pid, :rid, 'open_text', 3,
                            'CORE', :group, :team, :trading)
                    ON CONFLICT (question_code) DO NOTHING
                    """
                ),
                {
                    "code": code, "category": topic["category"], "text": text,
                    "pid": problem_id, "rid": root_cause_id, "group": _GROUP,
                    # Team & Leadership carries an explicit band even when
                    # anyone can answer: NULL means "not reviewed" for that
                    # pillar (d4a1f8c62b73 set every one of them), and 'solo'
                    # is how it says "anyone, including a founder alone".
                    "team": ("solo" if team is None and topic["pillar_id"] == 5
                             else team),
                    "trading": trading,
                },
            ).rowcount

    print(f"[{revision}] {problems} problems and {added_q} questions added to the "
          f"'{_GROUP}' bank")

    # A question in a category Exit withholds would be unreachable by the only
    # founders who can see this bank.
    from app.api.v1.diagnosis.stage_scope import EXIT_WITHHELD_CATEGORIES

    unreachable = bind.execute(
        sa.text(
            "SELECT question_code FROM questions "
            "WHERE primary_stage_group = :g AND category = ANY(:withheld)"
        ),
        {"g": _GROUP, "withheld": sorted(EXIT_WITHHELD_CATEGORIES)},
    ).scalars().all()
    if unreachable:
        raise RuntimeError(
            f"Exit questions in a category Exit withholds: {sorted(unreachable)}"
        )

    for pillar, n in bind.execute(
        sa.text(
            """
            SELECT p.pillar_id, count(*) FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE q.primary_stage_group = :g GROUP BY 1 ORDER BY 1
            """
        ),
        {"g": _GROUP},
    ).all():
        print(f"[{revision}]   pillar {pillar}: {n}")


def downgrade() -> None:
    bind = op.get_bind()
    codes = [q[0] for topic in _BANK for q in topic["questions"]]
    bind.execute(sa.text("DELETE FROM questions WHERE question_code = ANY(:c)"),
                 {"c": codes})
    bind.execute(
        sa.text("DELETE FROM root_causes WHERE root_cause_code = ANY(:c)"),
        {"c": [t["problem_code"].replace("EXT-", "RC-EXT-") for t in _BANK]},
    )
    bind.execute(sa.text("DELETE FROM problems WHERE problem_code = ANY(:c)"),
                 {"c": [t["problem_code"] for t in _BANK]})
    op.drop_constraint(_STAGE_GROUP_CHECK, "questions", type_="check")
    op.create_check_constraint(
        _STAGE_GROUP_CHECK, "questions",
        "primary_stage_group IN ("
        + ", ".join(f"'{g}'" for g in _GROUPS if g != _GROUP) + ")",
    )
