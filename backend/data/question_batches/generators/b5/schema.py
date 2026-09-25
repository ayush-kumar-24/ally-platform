# -*- coding: utf-8 -*-
"""Batch 5 (industries 21-25, A-Z order). Nine problems per industry: one for each
dimension code the three starved pillars allow, so every industry gets complete
dimension coverage rather than a partial fill.

QUESTION LANGUAGE. Every question here is written to be answered by a founder
reading it once, on a phone, at the end of a long day:
  - one idea, usually under fifteen words
  - everyday words; no "unit economics", "contribution margin", "ICP"
  - asks about something that happened, not about a concept
  - says "how many" or "how much" when a number is wanted
The pillar and dimension names stay technical because the engine reads them.
The founder never sees them.
"""

PILLAR = {"founder": 1, "team": 5, "strategy": 6}
QCAT = {"founder": "Founder Psychology", "team": "Team & Leadership",
        "strategy": "Strategy & Planning"}
DOMAIN = {"founder": "Founder Leverage", "team": "Team Effectiveness",
          "strategy": "Strategic Focus"}
STAGES = ["Stage 0", "Stage 0→1", "Stage 1→10+"]
SPREFIX = {"Stage 0": "S0", "Stage 0→1": "S01", "Stage 1→10+": "S10"}

# The nine dimension codes, in the order every industry supplies them.
DIM_ORDER = [
    ("founder",  "skill_stage_fit"),
    ("founder",  "time_allocation_reality"),
    ("founder",  "founder_dependency"),
    ("team",     "team_structure_role_clarity"),
    ("team",     "decision_rights"),
    ("team",     "hiring_repeatability"),
    ("strategy", "plan_to_vision_alignment"),
    ("strategy", "prioritization_discipline"),
    ("strategy", "institutional_memory"),
]

# Batch 5, in the canonical A-Z order.
INDUSTRIES = [
    ("logistics",        "LOG", "Logistics & Supply Chain"),
    ("adtech_marketing", "MKT", "Marketing, Advertising & AdTech"),
    ("ngo",              "NGO", "Non-Profit, Social Impact & NGO"),
    ("pharma_biotech",   "PHM", "Pharmaceuticals & Biotech"),
    ("services",         "SVC", "Professional Services & Consulting"),
]

# industry -> list of 9 entries, in DIM_ORDER.
# entry = (subcategory, problem_name, description, symptoms[],
#          [(rc_name, rc_category, explanation, weight)] x3,
#          [(steps[], principles[])] x2,
#          {stage: [(question, type, red_flag, green_flag)] x2})
CONTENT = {}
