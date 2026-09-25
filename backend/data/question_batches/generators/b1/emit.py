# -*- coding: utf-8 -*-
"""Emit batch 1 (industries 1-5, A-Z) as one idempotent SQL file."""
import sys, json, os
B = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, B)
from schema import PILLAR, QCAT, DOMAIN, STAGES, SPREFIX, DIM_ORDER, INDUSTRIES
from i01_agritech import AGRITECH
from i02_automotive import AUTOMOTIVE
from i03_fintech import FINTECH
from i04_beauty import BEAUTY
from i05_proptech import PROPTECH

CONTENT = {"agritech": AGRITECH, "automotive": AUTOMOTIVE, "fintech": FINTECH,
           "beauty_personal_care": BEAUTY, "proptech": PROPTECH}

# Start above every current maximum, leaving the earlier draft's block (800-834 etc.) alone.
PID, RID, QID, IID = 900, 4300, 5500, 1200

def q(s): return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"
def j(o): return q(json.dumps(o, ensure_ascii=False)) + "::jsonb"

out = [
 "-- Ally batch 1 (industries 1-5 in the agreed A-Z order):",
 "--   agritech, automotive, fintech, beauty_personal_care, proptech",
 "--",
 "-- Fills the three pillars the industry layer never covered -- Founder Readiness,",
 "-- Team & Leadership and Strategic Clarity -- across ALL NINE dimension codes,",
 "-- so each industry gets complete dimension coverage rather than a partial fill.",
 "-- Measured before this batch, across all 30 industries: Strategic Clarity had 0",
 "-- industry problems, Founder Readiness 2, Team & Leadership 14.",
 "--",
 "-- Questions are written in plain English: one idea, short, everyday words, and",
 "-- they ask about something that happened rather than about a concept.",
 "--",
 "-- Idempotent. Every insert is ON CONFLICT DO NOTHING on its unique code, ids are",
 "-- explicit and above the current maxima. Safe to run twice.",
 "BEGIN;",
]
c = dict(problems=0, root_causes=0, questions=0, interventions=0, mappings=0)

for icode, pfx, label in INDUSTRIES:
    entries = CONTENT[icode]
    assert len(entries) == len(DIM_ORDER), f"{icode}: expected {len(DIM_ORDER)} entries"
    out.append(f"\n-- ==================== {label} ({icode}) ====================")
    for n, (entry, (pkey, dim)) in enumerate(zip(entries, DIM_ORDER), start=1):
        subcat, pname, pdesc, symptoms, rcs, ivs, qs = entry
        pid, pcode = PID, f"{pfx}-2{n:02d}"; PID += 1
        out.append(f"-- {dim}")
        out.append(f"insert into problems (problem_id, problem_code, problem_name, category, layer,"
                   f" description, severity_min, severity_max, symptoms, pillar_id, subcategory,"
                   f" dimension_code, industry_relevance) values ({pid}, {q(pcode)}, {q(pname)},"
                   f" {q(QCAT[pkey])}, 'internal', {q(pdesc)}, 5, 9, {j(symptoms)}, {PILLAR[pkey]},"
                   f" {q(subcat)}, {q(dim)}, {j([icode])}) on conflict (problem_code) do nothing;")
        c["problems"] += 1
        rc_ids, rc_codes = [], []
        for k, (rname, rcat, rexp, rw) in enumerate(rcs, 1):
            rid, rcode = RID, f"RC-{pfx}-2{n:02d}-{k}"; RID += 1
            rc_ids.append(rid); rc_codes.append(rcode)
            out.append(f"insert into root_causes (root_cause_id, root_cause_code, problem_id,"
                       f" root_cause_name, root_cause_category, explanation, confidence_weight, layer,"
                       f" primary_stage_group, industry_relevance) values ({rid}, {q(rcode)}, {pid},"
                       f" {q(rname)}, {q(rcat)}, {q(rexp)}, {rw}, 'internal', 'Stage 0→1',"
                       f" {j([icode])}) on conflict (root_cause_code) do nothing;")
            c["root_causes"] += 1
        for k, (steps, principles) in enumerate(ivs, 1):
            iid, ic = IID, f"INT-{pfx}-2{n:02d}-{k}"; IID += 1
            out.append(f"insert into interventions (intervention_id, intervention_code, problem_id,"
                       f" root_cause_ids, capability_domain, section, recommended_frameworks,"
                       f" immediate_next_steps, stage_relevance, industry_relevance, design_principles,"
                       f" secondary_root_cause_ids) values ({iid}, {q(ic)}, {pid}, {j(rc_codes)},"
                       f" {q(DOMAIN[pkey])}, {q(label + ' — ' + subcat)}, '[]'::jsonb, {j(steps)},"
                       f" {j([3,4,5])}, {j([icode])}, {j(principles)}, '[]'::jsonb)"
                       f" on conflict (intervention_code) do nothing;")
            c["interventions"] += 1
        for stage in STAGES:
            for k, (qtext, qtype, red, green) in enumerate(qs[stage], 1):
                qid, qcode = QID, f"{SPREFIX[stage]}-{pfx}-2{n:02d}-{k}"; QID += 1
                out.append(f"insert into questions (question_id, question_code, category, question_text,"
                           f" problem_id, root_cause_id, question_type, difficulty_level, priority,"
                           f" is_distress_tagged, red_flag_pattern, green_flag_pattern,"
                           f" primary_stage_group, industry_relevance) values ({qid}, {q(qcode)},"
                           f" {q(QCAT[pkey])}, {q(qtext)}, {pid}, {rc_ids[(k-1) % len(rc_ids)]},"
                           f" {q(qtype)}, 2, 'CORE', false, {q(red)}, {q(green)}, {q(stage)},"
                           f" {j([icode])}) on conflict (question_code) do nothing;")
                c["questions"] += 1
                out.append(f"insert into question_industry_mapping (question_id, industry_code,"
                           f" stage_group, applicability_type) values ({qid}, {q(icode)}, {q(stage)},"
                           f" 'primary') on conflict (question_id, industry_code, stage_group) do nothing;")
                c["mappings"] += 1

out.append("\n-- Keep sequences ahead of the explicit ids.")
for t, col in (("problems","problem_id"),("root_causes","root_cause_id"),("questions","question_id"),
               ("interventions","intervention_id"),("question_industry_mapping","id")):
    out.append(f"select setval(pg_get_serial_sequence('{t}','{col}'), greatest((select max({col}) from {t}), 1));")
out.append("COMMIT;")

path = os.path.join(B, "ally_batch1_industries_1to5.sql")
open(path, "w").write("\n".join(out) + "\n")
print("written:", path)
print("rows:", c, "| total", sum(c.values()))
print("ids: problems 900..%d | root_causes 4300..%d | questions 5500..%d | interventions 1200..%d"
      % (PID-1, RID-1, QID-1, IID-1))
