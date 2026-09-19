"""The canonical capability taxonomy -- the shared semantic layer.

WHY THIS TABLE SET EXISTS. Ally can say what is wrong today. It cannot yet say
what a founder's intended destination REQUIRES, because there was no vocabulary
in which "what the business can do" could be stated once and then referenced
three times -- by a question (evidence), by a target (requirement) and by an
intervention (action). That vocabulary is this.

                        CAPABILITY
                       /     |     \\
               QUESTIONS   TARGET   INTERVENTIONS
                   |         |          |
               evidence  requirement  action

WHAT WAS NOT REUSED, AND WHY. Three existing vocabularies were considered:

  interventions.capability_domain  417 rows, ~390 near-unique free-text labels
                                   ("Opening Line Craft", "Sunk Cost Psychology")
                                   -- one label per intervention. A naming
                                   convention, not a taxonomy. Used here as a
                                   MAPPING SOURCE only.
  readiness_pillars (6)            diagnostic SCORING axes -- every description
                                   begins "Measures the founder's ability to".
                                   They rate the founder today; a capability is
                                   a thing the business can or cannot do. They
                                   are referenced (capabilities.pillar_id) so
                                   reports can group by a pillar the product
                                   already shows, but they are NOT the parent.
  interventions.section (12)       the same subject-area vocabulary as
                                   questions.category, plus five "Scaling --"
                                   entries. Subject areas, not capabilities:
                                   four of them are GTM-ish and one
                                   ("Idea & Validation") is really a stage.

So the taxonomy is new: 7 domains, 34 capabilities. Small on purpose. One
capability per durable thing a business can do, NOT one per intervention and
NOT one per root cause.

INDUSTRY-NEUTRAL BY CONSTRUCTION. There is no SaaS Sales Capability and no
Agriculture Sales Capability -- there is `GTM-SALES Repeatable Sales System`,
and the REQUIREMENT profile against it will differ by industry, business model,
stage and target scale when Step 6 builds capability_requirements. Duplicating
capabilities per industry would put the contextualisation in the wrong table and
make every industry a code change, which is the thing Steps 2-4 were spent
removing.

FOUNDER PSYCHOLOGY IS DELIBERATELY ABSENT. 75 of the 417 interventions are about
the founder's inner state ("Burnout Recovery", "Imposter Syndrome",
"Sunk Cost Psychology"). They are not mapped and that is not an omission: a
capability is something the BUSINESS can do, the Founder Readiness pillar and
the psychological_state engine already cover inner state, and collapsing the two
would make this a founder-personality taxonomy -- which it must not be. The
FOUNDER domain here is founder SCALABILITY (delegation, time, operational
independence), which is a property of the business.

NO LEVELS, NO REQUIREMENTS, NO GAPS IN THIS MIGRATION. The 0-3 level scale is
defined in app/api/v1/diagnosis/capability_levels.py and is not yet stored
anywhere, because nothing assesses a level yet. capability_requirements
(Step 6), capability_evidence (Step 8) and detected_gaps (Step 9) are
deliberately absent. In particular there is no MISSING state anywhere: a
capability with no evidence is UNASSESSED, and the distinction cannot be
weakened later by a schema that never had a word for it.

Purely additive and fully reversible. No existing table is altered, no existing
row is touched, and downgrade drops only what upgrade created.
"""

from alembic import op
import sqlalchemy as sa

revision = "f2a91c3d7b58"
down_revision = "e3f81a6c5d47"
branch_labels = None
depends_on = None


#: (domain_code, domain_name, description)
DOMAINS = [
    ('GTM', 'Go-to-Market & Revenue Engine', 'How reliably the business finds, wins and keeps customers.'),
    ('FOUNDER', 'Founder Scalability', 'How much of the business can run without the founder personally doing it.'),
    ('ORG', 'Organizational Scalability', 'Whether people other than the founder can own outcomes.'),
    ('OPS', 'Operational Scalability', 'Whether the work happens the same way twice without the founder watching.'),
    ('FIN', 'Financial Management & Planning', 'Whether the founder can see, plan and defend the numbers.'),
    ('PROD', 'Product & Delivery', 'Whether the right thing gets built and delivered predictably.'),
    ('STRAT', 'Strategic Clarity', 'Whether there is a coherent, defensible plan for where the business is going.'),
]

#: (capability_code, domain_code, capability_name, pillar_id, description)
#: `pillar_id` references readiness_pillars and is CONTEXTUAL METADATA -- it says
#: which existing scoring axis this capability reads against, so a report can
#: group capabilities under a heading founders already see. It is nullable and
#: nothing gates on it.
CAPABILITIES = [
    ('GTM-ICP', 'GTM', 'Customer & Segment Clarity', 2, 'Knowing precisely who the business sells to, and why they buy.'),
    ('GTM-ACQ', 'GTM', 'Repeatable Acquisition', 3, 'Whether new customers arrive through a channel that can be repeated on purpose.'),
    ('GTM-SALES', 'GTM', 'Repeatable Sales System', 3, 'A defined, teachable sales process rather than a series of improvisations.'),
    ('GTM-PIPE', 'GTM', 'Pipeline Visibility & Forecasting', 3, 'Knowing what is in the pipeline and what is likely to close.'),
    ('GTM-OWN', 'GTM', 'Sales Ownership Beyond the Founder', 5, 'Whether anyone other than the founder can win business.'),
    ('GTM-RETAIN', 'GTM', 'Retention & Expansion', 3, 'Whether existing customers stay, and grow.'),
    ('FND-TIME', 'FOUNDER', 'Founder Time Allocation', 1, "Whether the founder's time goes to what only the founder can do."),
    ('FND-DELEG', 'FOUNDER', 'Delegation & Decision Ownership', 5, 'Whether decisions have owners other than the founder.'),
    ('FND-INDEP', 'FOUNDER', 'Operational Independence from the Founder', 5, 'Whether the business keeps running when the founder steps away.'),
    ('FND-FOCUS', 'FOUNDER', 'Strategic Focus', 6, 'Whether the founder holds a direction rather than reacting to whatever is loudest.'),
    ('FND-LEAD', 'FOUNDER', 'Leadership Capacity', 5, 'Whether the founder can lead people, not just do the work.'),
    ('ORG-ROLES', 'ORG', 'Role Clarity & Ownership', 5, 'Whether responsibilities are defined and owned.'),
    ('ORG-HIRE', 'ORG', 'Hiring Capability', 5, 'Whether the business can define, attract and select the people it needs.'),
    ('ORG-PERF', 'ORG', 'Performance & Accountability', 5, 'Whether performance is visible, discussed and acted on.'),
    ('ORG-CADENCE', 'ORG', 'Management Cadence & Communication', 5, 'Whether the organisation has a rhythm for deciding and informing.'),
    ('ORG-CULTURE', 'ORG', 'Culture & Retention', 5, 'Whether people want to stay and know what is expected of them.'),
    ('OPS-PROCESS', 'OPS', 'Repeatable Processes', 4, 'Whether core work happens the same way each time.'),
    ('OPS-SOP', 'OPS', 'Documentation & SOPs', 4, 'Whether how-to knowledge lives outside individual heads.'),
    ('OPS-QUALITY', 'OPS', 'Quality Control', 4, 'Whether defects are caught before the customer finds them.'),
    ('OPS-MONITOR', 'OPS', 'Operational Monitoring', 4, 'Whether the founder can see operational health without asking someone.'),
    ('OPS-TOOLING', 'OPS', 'Systems & Tooling', 4, 'Whether the tools in use match the scale of the work.'),
    ('FIN-VIS', 'FIN', 'Financial Visibility', 3, 'Whether the founder can see the numbers, accurately and on time.'),
    ('FIN-UNIT', 'FIN', 'Unit Economics', 3, 'Whether the founder knows what each unit of business earns and costs.'),
    ('FIN-CASH', 'FIN', 'Cash & Runway Planning', 3, 'Whether cash is forecast rather than discovered.'),
    ('FIN-PLAN', 'FIN', 'Financial Planning & Budgeting', 3, 'Whether spending follows a plan that is reviewed.'),
    ('FIN-INVEST', 'FIN', 'Investor Readiness', 6, 'Whether the business can withstand external financial scrutiny.'),
    ('PRD-DISCOVER', 'PROD', 'Customer Discovery & Validation', 2, 'Whether what gets built is grounded in evidence from real customers.'),
    ('PRD-DELIVERY', 'PROD', 'Delivery Predictability', 4, 'Whether what is promised ships when it was said to.'),
    ('PRD-FEEDBACK', 'PROD', 'Feedback Loops', 4, 'Whether what customers experience gets back to the people building.'),
    ('PRD-ROADMAP', 'PROD', 'Roadmap & Prioritisation Discipline', 4, 'Whether what to build next is decided rather than reacted to.'),
    ('STR-POSITION', 'STRAT', 'Positioning & Differentiation', 6, 'Whether the business can say why it is the right choice.'),
    ('STR-MODEL', 'STRAT', 'Business Model Design', 6, 'Whether the way the business makes money is deliberate and sound.'),
    ('STR-COMPETE', 'STRAT', 'Competitive Awareness', 6, 'Whether decisions account for what the market is doing.'),
    ('STR-PLAN', 'STRAT', 'Planning & Goal Setting', 6, 'Whether there are goals, and whether progress against them is known.'),
]

#: capability_code -> observable criteria. These are STATEMENTS ABOUT THE
#: BUSINESS that an assessor could agree or disagree with, never scores and
#: never advice. They are what a future evidence extractor will test an answer
#: against, and what a report will quote when explaining a gap.
CRITERIA = {
    "GTM-ICP": [
        "The target customer is described in specifics, not adjectives",
        "Segments are distinguished by behaviour, not just size",
        "The reason customers buy is evidenced, not assumed",
        "Non-customers are as clearly defined as customers"
    ],
    "GTM-ACQ": [
        "At least one channel produces customers predictably",
        "Channel choice is based on measured results",
        "Acquisition activity happens on a cadence, not in bursts",
        "Cost per acquired customer is known"
    ],
    "GTM-SALES": [
        "A sales process exists and is written down",
        "The same steps are followed across deals",
        "Objections have prepared responses",
        "A new seller could follow the process without the founder"
    ],
    "GTM-PIPE": [
        "Open opportunities are visible in one place",
        "Deal stages mean the same thing to everyone",
        "Close rate is known rather than estimated",
        "Lost deals are reviewed for cause"
    ],
    "GTM-OWN": [
        "Someone other than the founder closes business",
        "Sales targets are owned by a named person",
        "The founder is not required for a routine deal",
        "Sales performance is reviewed with the owner"
    ],
    "GTM-RETAIN": [
        "Churn is measured",
        "Renewal or repeat purchase is managed, not hoped for",
        "Customer issues have a route to resolution",
        "Expansion within existing customers is deliberate"
    ],
    "FND-TIME": [
        "The founder's time is spent on work only they can do",
        "Routine work has been moved off the founder",
        "The founder's week has a deliberate shape",
        "Time spent firefighting is falling"
    ],
    "FND-DELEG": [
        "Decisions have named owners",
        "Routine decisions do not reach the founder",
        "Delegated work comes with authority, not just the task",
        "The founder can name what they no longer decide"
    ],
    "FND-INDEP": [
        "The business operates when the founder is away",
        "Critical knowledge is not only in the founder's head",
        "Customers are not dependent on the founder personally",
        "No single process stops without the founder"
    ],
    "FND-FOCUS": [
        "There is a stated priority for the current period",
        "New opportunities are evaluated against it",
        "Work that does not serve it is declined",
        "The priority survives contact with a busy week"
    ],
    "FND-LEAD": [
        "The founder leads through others rather than doing",
        "Direction is communicated, not assumed",
        "Difficult conversations happen rather than being avoided",
        "The founder's own development is deliberate"
    ],
    "ORG-ROLES": [
        "Every role has a written scope",
        "Ownership of each outcome is unambiguous",
        "Gaps and overlaps in responsibility are known",
        "Role scope is revisited as the business changes"
    ],
    "ORG-HIRE": [
        "A role is defined before hiring for it",
        "There is a consistent bar across hires",
        "New joiners have a structured first month",
        "Hiring outcomes are reviewed"
    ],
    "ORG-PERF": [
        "Expectations are explicit",
        "Performance is discussed on a schedule, not ad hoc",
        "Good and poor performance are both addressed",
        "Performance history is recorded somewhere durable"
    ],
    "ORG-CADENCE": [
        "There is a regular rhythm of team meetings",
        "Decisions and their reasoning are recorded",
        "Information reaches the people who need it",
        "The cadence survives busy periods"
    ],
    "ORG-CULTURE": [
        "What the business expects of people is explicit",
        "People stay longer than the founder fears",
        "Concerns surface before they become exits",
        "The founder models what they ask for"
    ],
    "OPS-PROCESS": [
        "Core work follows the same steps each time",
        "Handoffs between people are defined",
        "Exceptions are recognised as exceptions",
        "Process changes are deliberate"
    ],
    "OPS-SOP": [
        "How-to knowledge is written down",
        "Documentation is findable by the people who need it",
        "Documents are updated rather than abandoned",
        "Someone absent does not stop the work"
    ],
    "OPS-QUALITY": [
        "Quality is defined before work starts",
        "Defects are caught before the customer sees them",
        "Rework is measured",
        "Recurring defects trigger a process change"
    ],
    "OPS-MONITOR": [
        "Operational health is visible without asking",
        "The numbers watched are the ones that matter",
        "Problems are noticed rather than reported by customers",
        "Monitoring drives action, not just reporting"
    ],
    "OPS-TOOLING": [
        "Tools match the scale of the work",
        "Data lives in systems rather than spreadsheets and heads",
        "Manual steps that create risk are known",
        "Tool changes are evaluated, not accumulated"
    ],
    "FIN-VIS": [
        "Financial statements are produced on a schedule",
        "The founder can read and interpret them",
        "Numbers are trusted enough to decide on",
        "Reports lead to action"
    ],
    "FIN-UNIT": [
        "The revenue and cost of one unit of business are known",
        "Pricing is set deliberately",
        "Margin by product or segment is visible",
        "Discounting is bounded"
    ],
    "FIN-CASH": [
        "Cash position is known at any time",
        "Runway is forecast rather than discovered",
        "Receivables and payables are tracked",
        "A cash-tight scenario has been thought through"
    ],
    "FIN-PLAN": [
        "There is a budget",
        "Spending is reviewed against it",
        "Plans are revised when reality moves",
        "Major spend has an approval path"
    ],
    "FIN-INVEST": [
        "Financials would survive outside scrutiny",
        "The equity and cap position is clean and known",
        "The business can be explained in investor terms",
        "Commitments made to investors are tracked"
    ],
    "PRD-DISCOVER": [
        "Build decisions cite evidence from real customers",
        "Assumptions are identified as assumptions",
        "Disconfirming evidence is sought, not avoided",
        "Validation happens before significant build"
    ],
    "PRD-DELIVERY": [
        "What is promised ships when it was said to",
        "Scope and date are managed explicitly",
        "Slippage is visible early",
        "Delivery does not depend on heroics"
    ],
    "PRD-FEEDBACK": [
        "Customer experience reaches the people building",
        "Feedback is collected systematically",
        "Feedback changes what gets built",
        "The loop closes back to the customer"
    ],
    "PRD-ROADMAP": [
        "What comes next is decided, not reacted to",
        "Prioritisation has stated criteria",
        "Saying no is possible",
        "The roadmap survives a loud customer request"
    ],
    "STR-POSITION": [
        "The business can say why it is the right choice",
        "Positioning is consistent across channels",
        "Differentiation is real, not claimed",
        "Messaging is specific enough to exclude someone"
    ],
    "STR-MODEL": [
        "How the business makes money is deliberate",
        "The model has been tested, not just designed",
        "Revenue streams are understood individually",
        "Model changes are evaluated before adoption"
    ],
    "STR-COMPETE": [
        "Who else the customer considers is known",
        "Competitive information is gathered, not guessed",
        "Losses to competitors are understood",
        "Strategy accounts for what the market is doing"
    ],
    "STR-PLAN": [
        "There are stated goals for a defined period",
        "Progress against them is known",
        "Risks to the plan are identified and owned",
        "The plan is revised rather than abandoned"
    ]
}

#: (intervention_code, capability_code), derived from interventions.
#: capability_domain by reviewed keyword rules and then checked by hand. 354
#: pairs over 328 of 417 interventions. The remaining 89 are NOT mapped:
#: 75 are founder-psychology (out of scope, see the module docstring) and 14 are
#: genuinely ambiguous. Forcing those would have put noise into the one table
#: three later steps depend on, so they are reported instead -- see
#: backend/docs/CAPABILITY-TAXONOMY.md.
INTERVENTION_CAPABILITIES = [
    ('INT-045', 'ORG-ROLES'),
    ('INT-046', 'OPS-PROCESS'),
    ('INT-047', 'OPS-SOP'),
    ('INT-048', 'FND-DELEG'),
    ('INT-049', 'ORG-CADENCE'),
    ('INT-050', 'ORG-CADENCE'),
    ('INT-052', 'OPS-QUALITY'),
    ('INT-054', 'OPS-PROCESS'),
    ('INT-055', 'FND-LEAD'),
    ('INT-056', 'GTM-OWN'),
    ('INT-057', 'FIN-UNIT'),
    ('INT-058', 'OPS-TOOLING'),
    ('INT-059', 'GTM-RETAIN'),
    ('INT-060', 'FIN-PLAN'),
    ('INT-060', 'GTM-PIPE'),
    ('INT-061', 'FIN-VIS'),
    ('INT-062', 'FIN-CASH'),
    ('INT-063', 'FIN-UNIT'),
    ('INT-064', 'GTM-OWN'),
    ('INT-066', 'GTM-RETAIN'),
    ('INT-067', 'FIN-PLAN'),
    ('INT-068', 'FND-LEAD'),
    ('INT-069', 'ORG-PERF'),
    ('INT-070', 'ORG-ROLES'),
    ('INT-072', 'ORG-CULTURE'),
    ('INT-073', 'ORG-PERF'),
    ('INT-074', 'ORG-CADENCE'),
    ('INT-075', 'ORG-PERF'),
    ('INT-076', 'ORG-ROLES'),
    ('INT-077', 'ORG-CULTURE'),
    ('INT-078', 'STR-COMPETE'),
    ('INT-079', 'STR-POSITION'),
    ('INT-080', 'GTM-RETAIN'),
    ('INT-081', 'STR-POSITION'),
    ('INT-082', 'PRD-ROADMAP'),
    ('INT-083', 'STR-MODEL'),
    ('INT-084', 'GTM-RETAIN'),
    ('INT-085', 'STR-MODEL'),
    ('INT-086', 'STR-MODEL'),
    ('INT-087', 'FND-LEAD'),
    ('INT-088', 'FND-DELEG'),
    ('INT-089', 'ORG-ROLES'),
    ('INT-090', 'FIN-INVEST'),
    ('INT-091', 'FIN-INVEST'),
    ('INT-093', 'FND-LEAD'),
    ('INT-125', 'PRD-DISCOVER'),
    ('INT-126', 'GTM-ICP'),
    ('INT-127', 'STR-COMPETE'),
    ('INT-128', 'FIN-UNIT'),
    ('INT-129', 'FIN-UNIT'),
    ('INT-130', 'FIN-UNIT'),
    ('INT-131', 'FIN-UNIT'),
    ('INT-132', 'STR-COMPETE'),
    ('INT-133', 'STR-PLAN'),
    ('INT-134', 'STR-MODEL'),
    ('INT-135', 'PRD-ROADMAP'),
    ('INT-136', 'FND-FOCUS'),
    ('INT-137', 'PRD-ROADMAP'),
    ('INT-138', 'OPS-PROCESS'),
    ('INT-139', 'FIN-PLAN'),
    ('INT-140', 'FIN-PLAN'),
    ('INT-141', 'STR-PLAN'),
    ('INT-142', 'STR-PLAN'),
    ('INT-143', 'STR-PLAN'),
    ('INT-144', 'GTM-ICP'),
    ('INT-145', 'GTM-ICP'),
    ('INT-146', 'STR-POSITION'),
    ('INT-147', 'STR-COMPETE'),
    ('INT-149', 'PRD-ROADMAP'),
    ('INT-150', 'ORG-CADENCE'),
    ('INT-151', 'OPS-PROCESS'),
    ('INT-152', 'STR-PLAN'),
    ('INT-153', 'STR-PLAN'),
    ('INT-154', 'PRD-DISCOVER'),
    ('INT-157', 'GTM-SALES'),
    ('INT-158', 'GTM-SALES'),
    ('INT-159', 'GTM-PIPE'),
    ('INT-160', 'GTM-SALES'),
    ('INT-161', 'GTM-RETAIN'),
    ('INT-162', 'GTM-ACQ'),
    ('INT-163', 'GTM-ACQ'),
    ('INT-164', 'GTM-ACQ'),
    ('INT-165', 'GTM-ACQ'),
    ('INT-166', 'FIN-CASH'),
    ('INT-166', 'OPS-MONITOR'),
    ('INT-167', 'FIN-CASH'),
    ('INT-167', 'GTM-PIPE'),
    ('INT-168', 'FIN-VIS'),
    ('INT-169', 'FIN-PLAN'),
    ('INT-170', 'FIN-VIS'),
    ('INT-171', 'FIN-VIS'),
    ('INT-172', 'ORG-HIRE'),
    ('INT-173', 'OPS-MONITOR'),
    ('INT-173', 'ORG-PERF'),
    ('INT-174', 'OPS-SOP'),
    ('INT-175', 'OPS-SOP'),
    ('INT-176', 'GTM-PIPE'),
    ('INT-177', 'GTM-ACQ'),
    ('INT-178', 'GTM-SALES'),
    ('INT-179', 'GTM-SALES'),
    ('INT-179', 'PRD-DISCOVER'),
    ('INT-180', 'GTM-ACQ'),
    ('INT-181', 'GTM-ACQ'),
    ('INT-182', 'GTM-SALES'),
    ('INT-183', 'GTM-ACQ'),
    ('INT-184', 'GTM-SALES'),
    ('INT-185', 'GTM-SALES'),
    ('INT-186', 'GTM-SALES'),
    ('INT-187', 'GTM-SALES'),
    ('INT-189', 'GTM-SALES'),
    ('INT-190', 'GTM-SALES'),
    ('INT-190', 'OPS-MONITOR'),
    ('INT-191', 'GTM-SALES'),
    ('INT-191', 'ORG-PERF'),
    ('INT-192', 'GTM-PIPE'),
    ('INT-193', 'GTM-PIPE'),
    ('INT-194', 'GTM-PIPE'),
    ('INT-195', 'STR-COMPETE'),
    ('INT-196', 'GTM-PIPE'),
    ('INT-197', 'GTM-PIPE'),
    ('INT-197', 'OPS-MONITOR'),
    ('INT-198', 'GTM-ICP'),
    ('INT-198', 'GTM-PIPE'),
    ('INT-199', 'FIN-UNIT'),
    ('INT-199', 'GTM-PIPE'),
    ('INT-200', 'GTM-RETAIN'),
    ('INT-201', 'GTM-RETAIN'),
    ('INT-202', 'GTM-ACQ'),
    ('INT-202', 'GTM-RETAIN'),
    ('INT-203', 'GTM-RETAIN'),
    ('INT-204', 'GTM-ACQ'),
    ('INT-205', 'GTM-ACQ'),
    ('INT-206', 'GTM-ACQ'),
    ('INT-207', 'GTM-ACQ'),
    ('INT-209', 'STR-POSITION'),
    ('INT-210', 'OPS-TOOLING'),
    ('INT-211', 'OPS-QUALITY'),
    ('INT-212', 'GTM-ACQ'),
    ('INT-213', 'GTM-SALES'),
    ('INT-214', 'GTM-ACQ'),
    ('INT-216', 'GTM-ACQ'),
    ('INT-217', 'GTM-PIPE'),
    ('INT-218', 'GTM-ACQ'),
    ('INT-218', 'GTM-ICP'),
    ('INT-219', 'ORG-PERF'),
    ('INT-220', 'GTM-ACQ'),
    ('INT-221', 'FIN-CASH'),
    ('INT-221', 'OPS-MONITOR'),
    ('INT-222', 'FIN-CASH'),
    ('INT-222', 'OPS-MONITOR'),
    ('INT-223', 'FIN-CASH'),
    ('INT-223', 'GTM-PIPE'),
    ('INT-224', 'FIN-CASH'),
    ('INT-225', 'FIN-CASH'),
    ('INT-226', 'FIN-INVEST'),
    ('INT-227', 'FIN-CASH'),
    ('INT-229', 'FIN-UNIT'),
    ('INT-230', 'FIN-CASH'),
    ('INT-230', 'FIN-VIS'),
    ('INT-231', 'FIN-VIS'),
    ('INT-232', 'FIN-UNIT'),
    ('INT-233', 'FIN-PLAN'),
    ('INT-234', 'FIN-PLAN'),
    ('INT-235', 'FIN-PLAN'),
    ('INT-236', 'FIN-PLAN'),
    ('INT-237', 'FIN-PLAN'),
    ('INT-238', 'FIN-UNIT'),
    ('INT-239', 'FIN-UNIT'),
    ('INT-240', 'FIN-VIS'),
    ('INT-241', 'FIN-VIS'),
    ('INT-242', 'FIN-VIS'),
    ('INT-243', 'FIN-VIS'),
    ('INT-244', 'FIN-VIS'),
    ('INT-245', 'FIN-VIS'),
    ('INT-246', 'ORG-HIRE'),
    ('INT-247', 'ORG-ROLES'),
    ('INT-248', 'ORG-HIRE'),
    ('INT-249', 'ORG-HIRE'),
    ('INT-250', 'ORG-PERF'),
    ('INT-251', 'ORG-PERF'),
    ('INT-252', 'ORG-PERF'),
    ('INT-253', 'OPS-MONITOR'),
    ('INT-253', 'ORG-PERF'),
    ('INT-254', 'ORG-PERF'),
    ('INT-255', 'OPS-SOP'),
    ('INT-256', 'OPS-SOP'),
    ('INT-257', 'OPS-SOP'),
    ('INT-259', 'OPS-SOP'),
    ('INT-260', 'OPS-SOP'),
    ('INT-261', 'OPS-SOP'),
    ('INT-261', 'STR-PLAN'),
    ('INT-262', 'OPS-SOP'),
    ('INT-263', 'GTM-ACQ'),
    ('INT-264', 'GTM-ACQ'),
    ('INT-265', 'GTM-ACQ'),
    ('INT-266', 'GTM-ACQ'),
    ('INT-267', 'GTM-ACQ'),
    ('INT-269', 'GTM-SALES'),
    ('INT-271', 'GTM-PIPE'),
    ('INT-272', 'PRD-DISCOVER'),
    ('INT-276', 'PRD-DISCOVER'),
    ('INT-279', 'PRD-DISCOVER'),
    ('INT-279', 'STR-COMPETE'),
    ('INT-280', 'STR-PLAN'),
    ('INT-282', 'GTM-ICP'),
    ('INT-283', 'FND-FOCUS'),
    ('INT-284', 'STR-POSITION'),
    ('INT-285', 'PRD-DISCOVER'),
    ('INT-287', 'GTM-SALES'),
    ('INT-289', 'ORG-CADENCE'),
    ('INT-291', 'ORG-CADENCE'),
    ('INT-292', 'PRD-FEEDBACK'),
    ('INT-293', 'PRD-FEEDBACK'),
    ('INT-294', 'PRD-DISCOVER'),
    ('INT-296', 'PRD-ROADMAP'),
    ('INT-300', 'GTM-ICP'),
    ('INT-301', 'FND-FOCUS'),
    ('INT-302', 'GTM-ACQ'),
    ('INT-302', 'OPS-TOOLING'),
    ('INT-303', 'GTM-ACQ'),
    ('INT-304', 'GTM-ACQ'),
    ('INT-305', 'GTM-ICP'),
    ('INT-306', 'STR-POSITION'),
    ('INT-307', 'STR-POSITION'),
    ('INT-308', 'FIN-UNIT'),
    ('INT-309', 'FIN-UNIT'),
    ('INT-310', 'FIN-UNIT'),
    ('INT-311', 'GTM-SALES'),
    ('INT-312', 'GTM-SALES'),
    ('INT-314', 'GTM-RETAIN'),
    ('INT-316', 'GTM-RETAIN'),
    ('INT-317', 'GTM-ACQ'),
    ('INT-318', 'STR-POSITION'),
    ('INT-319', 'FND-FOCUS'),
    ('INT-320', 'GTM-SALES'),
    ('INT-321', 'GTM-SALES'),
    ('INT-322', 'GTM-SALES'),
    ('INT-323', 'FIN-UNIT'),
    ('INT-324', 'FIN-UNIT'),
    ('INT-325', 'FIN-UNIT'),
    ('INT-326', 'FIN-UNIT'),
    ('INT-328', 'FIN-UNIT'),
    ('INT-329', 'GTM-RETAIN'),
    ('INT-330', 'PRD-DELIVERY'),
    ('INT-332', 'GTM-RETAIN'),
    ('INT-333', 'GTM-SALES'),
    ('INT-334', 'ORG-HIRE'),
    ('INT-335', 'ORG-ROLES'),
    ('INT-336', 'ORG-CULTURE'),
    ('INT-337', 'ORG-CULTURE'),
    ('INT-338', 'FND-DELEG'),
    ('INT-340', 'ORG-CULTURE'),
    ('INT-342', 'STR-MODEL'),
    ('INT-343', 'ORG-HIRE'),
    ('INT-345', 'ORG-HIRE'),
    ('INT-348', 'ORG-CADENCE'),
    ('INT-349', 'FND-DELEG'),
    ('INT-350', 'FND-DELEG'),
    ('INT-351', 'ORG-CULTURE'),
    ('INT-352', 'ORG-CADENCE'),
    ('INT-353', 'ORG-HIRE'),
    ('INT-355', 'FIN-INVEST'),
    ('INT-356', 'FIN-INVEST'),
    ('INT-357', 'GTM-SALES'),
    ('INT-358', 'FIN-INVEST'),
    ('INT-359', 'FIN-INVEST'),
    ('INT-360', 'FIN-INVEST'),
    ('INT-361', 'FIN-INVEST'),
    ('INT-362', 'STR-COMPETE'),
    ('INT-363', 'FIN-INVEST'),
    ('INT-366', 'FIN-INVEST'),
    ('INT-367', 'FIN-INVEST'),
    ('INT-368', 'STR-POSITION'),
    ('INT-369', 'FIN-INVEST'),
    ('INT-370', 'FIN-INVEST'),
    ('INT-371', 'FIN-INVEST'),
    ('INT-372', 'FIN-INVEST'),
    ('INT-373', 'FND-INDEP'),
    ('INT-374', 'FIN-CASH'),
    ('INT-375', 'FIN-INVEST'),
    ('INT-376', 'FND-FOCUS'),
    ('INT-377', 'PRD-ROADMAP'),
    ('INT-378', 'FND-DELEG'),
    ('INT-379', 'ORG-CADENCE'),
    ('INT-380', 'FND-FOCUS'),
    ('INT-381', 'PRD-FEEDBACK'),
    ('INT-382', 'FND-FOCUS'),
    ('INT-382', 'STR-PLAN'),
    ('INT-383', 'FND-INDEP'),
    ('INT-384', 'FND-FOCUS'),
    ('INT-385', 'GTM-RETAIN'),
    ('INT-385', 'OPS-QUALITY'),
    ('INT-386', 'STR-POSITION'),
    ('INT-387', 'PRD-FEEDBACK'),
    ('INT-388', 'GTM-ICP'),
    ('INT-389', 'PRD-DISCOVER'),
    ('INT-390', 'PRD-DISCOVER'),
    ('INT-391', 'FIN-UNIT'),
    ('INT-394', 'PRD-DISCOVER'),
    ('INT-395', 'PRD-DELIVERY'),
    ('INT-397', 'OPS-PROCESS'),
    ('INT-398', 'FND-FOCUS'),
    ('INT-399', 'FND-FOCUS'),
    ('INT-399', 'STR-PLAN'),
    ('INT-400', 'FND-INDEP'),
    ('INT-401', 'FND-TIME'),
    ('INT-402', 'FND-DELEG'),
    ('INT-404', 'FND-DELEG'),
    ('INT-405', 'OPS-QUALITY'),
    ('INT-406', 'STR-PLAN'),
    ('INT-407', 'ORG-ROLES'),
    ('INT-408', 'OPS-TOOLING'),
    ('INT-409', 'FIN-VIS'),
    ('INT-410', 'FIN-VIS'),
    ('INT-411', 'OPS-MONITOR'),
    ('INT-411', 'OPS-TOOLING'),
    ('INT-413', 'OPS-TOOLING'),
    ('INT-414', 'STR-PLAN'),
    ('INT-415', 'ORG-PERF'),
    ('INT-421', 'FND-DELEG'),
    ('INT-425', 'GTM-ICP'),
    ('INT-428', 'FND-TIME'),
    ('INT-429', 'FND-DELEG'),
    ('INT-430', 'FND-DELEG'),
    ('INT-431', 'OPS-SOP'),
    ('INT-435', 'FND-DELEG'),
    ('INT-436', 'FND-DELEG'),
    ('INT-436', 'PRD-DELIVERY'),
    ('INT-437', 'STR-PLAN'),
    ('INT-439', 'FND-DELEG'),
    ('INT-442', 'PRD-DISCOVER'),
    ('INT-451', 'OPS-PROCESS'),
    ('INT-453', 'FND-TIME'),
    ('INT-454', 'FND-TIME'),
    ('INT-456', 'ORG-PERF'),
    ('INT-457', 'FND-LEAD'),
    ('INT-461', 'FND-LEAD'),
    ('INT-462', 'FND-DELEG'),
    ('INT-465', 'OPS-PROCESS'),
    ('INT-467', 'FND-TIME'),
    ('INT-474', 'FND-TIME'),
    ('INT-475', 'FND-TIME'),
    ('INT-476', 'PRD-DISCOVER'),
    ('INT-480', 'PRD-DISCOVER'),
    ('INT-483', 'STR-PLAN'),
    ('INT-488', 'ORG-CULTURE'),
    ('INT-489', 'GTM-ACQ'),
    ('INT-490', 'GTM-ACQ'),
    ('INT-493', 'PRD-FEEDBACK'),
    ('INT-494', 'GTM-ACQ'),
    ('INT-495', 'FIN-CASH'),
    ('INT-495', 'OPS-MONITOR'),
    ('INT-497', 'OPS-SOP'),
    ('INT-498', 'OPS-SOP'),
]


def upgrade() -> None:
    op.create_table(
        "capability_domains",
        sa.Column("domain_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("domain_code", sa.String(length=20), nullable=False),
        sa.Column("domain_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("domain_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("domain_id", name="capability_domains_pkey"),
        sa.UniqueConstraint("domain_code", name="capability_domains_domain_code_key"),
    )

    op.create_table(
        "capabilities",
        sa.Column("capability_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability_code", sa.String(length=30), nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=False),
        sa.Column("capability_name", sa.String(length=120), nullable=False),
        # Contextual metadata, nullable, nothing gates on it. See the module
        # docstring: pillars are scoring axes, not the taxonomy's parent.
        sa.Column("pillar_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("capability_id", name="capabilities_pkey"),
        sa.UniqueConstraint("capability_code", name="capabilities_capability_code_key"),
        sa.ForeignKeyConstraint(["domain_id"], ["capability_domains.domain_id"],
                                name="capabilities_domain_id_fkey"),
        sa.ForeignKeyConstraint(["pillar_id"], ["readiness_pillars.pillar_id"],
                                name="capabilities_pillar_id_fkey"),
    )
    op.create_index("idx_capabilities_domain", "capabilities", ["domain_id"])

    op.create_table(
        "capability_evidence_criteria",
        sa.Column("criterion_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("criterion_text", sa.Text(), nullable=False),
        sa.Column("criterion_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("criterion_id", name="capability_evidence_criteria_pkey"),
        sa.ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                                ondelete="CASCADE",
                                name="capability_evidence_criteria_capability_id_fkey"),
        sa.UniqueConstraint("capability_id", "criterion_order",
                            name="uq_capability_evidence_criteria_order"),
    )

    op.create_table(
        "intervention_capabilities",
        sa.Column("intervention_id", sa.Integer(), nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        # The composite key IS the uniqueness rule: one intervention may build
        # several capabilities, but never the same one twice.
        sa.PrimaryKeyConstraint("intervention_id", "capability_id",
                                name="intervention_capabilities_pkey"),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.intervention_id"],
                                ondelete="CASCADE",
                                name="intervention_capabilities_intervention_id_fkey"),
        sa.ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                                ondelete="CASCADE",
                                name="intervention_capabilities_capability_id_fkey"),
    )
    op.create_index("idx_intervention_capabilities_capability",
                    "intervention_capabilities", ["capability_id"])

    # Infrastructure only -- deliberately seeded with NOTHING. Mapping ~3,460
    # questions is a curation pass, not a migration, and a fabricated mapping
    # would produce confident evidence about capabilities nobody checked. An
    # unmapped question simply yields no capability evidence, which is the same
    # fail-open every other optional map in this codebase uses.
    op.create_table(
        "question_capabilities",
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("question_id", "capability_id",
                                name="question_capabilities_pkey"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.question_id"],
                                ondelete="CASCADE",
                                name="question_capabilities_question_id_fkey"),
        sa.ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                                ondelete="CASCADE",
                                name="question_capabilities_capability_id_fkey"),
    )
    op.create_index("idx_question_capabilities_capability",
                    "question_capabilities", ["capability_id"])

    _seed()


def _seed() -> None:
    conn = op.get_bind()

    domain_ids = {}
    for order, (code, name, description) in enumerate(DOMAINS, start=1):
        domain_ids[code] = conn.execute(sa.text(
            "INSERT INTO capability_domains"
            " (domain_code, domain_name, description, domain_order)"
            " VALUES (:c, :n, :d, :o) RETURNING domain_id"
        ), {"c": code, "n": name, "d": description, "o": order}).scalar()

    capability_ids = {}
    for code, domain_code, name, pillar_id, description in CAPABILITIES:
        capability_ids[code] = conn.execute(sa.text(
            "INSERT INTO capabilities"
            " (capability_code, domain_id, capability_name, pillar_id, description)"
            " VALUES (:c, :d, :n, :p, :desc) RETURNING capability_id"
        ), {"c": code, "d": domain_ids[domain_code], "n": name,
            "p": pillar_id, "desc": description}).scalar()

    for capability_code, criteria in CRITERIA.items():
        for order, text_ in enumerate(criteria, start=1):
            conn.execute(sa.text(
                "INSERT INTO capability_evidence_criteria"
                " (capability_id, criterion_text, criterion_order)"
                " VALUES (:c, :t, :o)"
            ), {"c": capability_ids[capability_code], "t": text_, "o": order})

    # Joined on intervention_code rather than intervention_id: ids are
    # environment-specific, codes are the stable identifier. An intervention
    # code absent from this database is skipped rather than failing the
    # migration -- the mapping is reference data, not a constraint on the
    # library.
    for intervention_code, capability_code in INTERVENTION_CAPABILITIES:
        conn.execute(sa.text(
            "INSERT INTO intervention_capabilities (intervention_id, capability_id)"
            " SELECT i.intervention_id, :cap FROM interventions i"
            "  WHERE i.intervention_code = :icode"
            " ON CONFLICT DO NOTHING"
        ), {"cap": capability_ids[capability_code], "icode": intervention_code})


def downgrade() -> None:
    # Child tables first; each drop takes its own indexes with it.
    op.drop_table("question_capabilities")
    op.drop_table("intervention_capabilities")
    op.drop_table("capability_evidence_criteria")
    op.drop_table("capabilities")
    op.drop_table("capability_domains")
