# -*- coding: utf-8 -*-
"""Batch 1, emitted with NO hardcoded ids.

Why: the production database (RDS) cannot be read from the build environment, so
its id maxima are unknown. A file with explicit primary keys either collides and
rolls back, or needs a pre-check and a re-emit. This version removes the problem
instead of managing it:

  * every insert lets the sequence assign the primary key
  * every foreign key is resolved by CODE at insert time, via a subselect
  * intervention.root_cause_ids already held codes, so it is unchanged
  * the sequences are pushed above max(id) first, which repairs the common case
    where earlier explicit-id loads left a sequence behind its own table

Result: the same file applies to any database carrying the schema, whatever its
ids, and is safe to run twice.
"""
import sys, json, os
B = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, B)
from schema import PILLAR, QCAT, DOMAIN, STAGES, SPREFIX, DIM_ORDER, INDUSTRIES
from i06_consumer_electronics import CONSUMER_ELECTRONICS
from i07_ecommerce import ECOMMERCE
from i08_edtech import EDTECH
from i09_cleantech import CLEANTECH
from i10_media import MEDIA

CONTENT = {"consumer_electronics": CONSUMER_ELECTRONICS, "ecommerce_d2c": ECOMMERCE, "edtech": EDTECH,
           "cleantech_energy": CLEANTECH, "media_entertainment": MEDIA}

def q(s): return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"
def j(o): return q(json.dumps(o, ensure_ascii=False)) + "::jsonb"
def pref(code): return f"(select problem_id from problems where problem_code = {q(code)})"
def rref(code): return f"(select root_cause_id from root_causes where root_cause_code = {q(code)})"
def qref(code): return f"(select question_id from questions where question_code = {q(code)})"

out = [
 "-- =====================================================================",
 "-- Ally — industry content batch 2 (industries 6-10, A-Z order)",
 "--   consumer_electronics, ecommerce_d2c, edtech, cleantech_energy, media_entertainment",
 "--",
 "-- 810 rows: 45 problems, 135 root causes, 90 interventions,",
 "--           270 questions, 270 question_industry_mapping rows.",
 "--",
 "-- INSERT ONLY. No schema change. Nothing existing is altered or deleted.",
 "--",
 "-- NO HARDCODED IDS. Primary keys come from the sequences; every foreign key",
 "-- is resolved by code at insert time. There is nothing to collide with, so",
 "-- no id pre-check is needed and the file needs no edits for this database.",
 "--",
 "-- SAFE TO RUN TWICE. Every insert is ON CONFLICT DO NOTHING on its unique",
 "-- code. A second run inserts nothing and reports no error.",
 "--",
 "-- Runs as ONE transaction: you get all 810 rows or none.",
 "--   psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -f <this file>",
 "-- =====================================================================",
 "",
 "BEGIN;",
 "",
 "-- Push each sequence above its table's current max. Harmless if already ahead;",
 "-- repairs the case where an earlier explicit-id load left the sequence behind,",
 "-- which would otherwise make the inserts below collide.",
]
for t, col in (("problems","problem_id"),("root_causes","root_cause_id"),
               ("questions","question_id"),("interventions","intervention_id"),
               ("question_industry_mapping","id")):
    out.append(f"select setval(pg_get_serial_sequence('{t}','{col}'), "
               f"greatest((select coalesce(max({col}),0) from {t}), 1));")

c = dict(problems=0, root_causes=0, questions=0, interventions=0, mappings=0)

for icode, pfx, label in INDUSTRIES:
    entries = CONTENT[icode]
    out.append(f"\n-- =============== {label}  ({icode}) ===============")
    for n, (entry, (pkey, dim)) in enumerate(zip(entries, DIM_ORDER), start=1):
        subcat, pname, pdesc, symptoms, rcs, ivs, qs = entry
        pcode = f"{pfx}-3{n:02d}"
        out.append(f"\n-- {pcode} · {dim} · {pname}")
        out.append(f"insert into problems (problem_code, problem_name, category, layer, description,"
                   f" severity_min, severity_max, symptoms, pillar_id, subcategory, dimension_code,"
                   f" industry_relevance) values ({q(pcode)}, {q(pname)}, {q(QCAT[pkey])}, 'internal',"
                   f" {q(pdesc)}, 5, 9, {j(symptoms)}, {PILLAR[pkey]}, {q(subcat)}, {q(dim)},"
                   f" {j([icode])}) on conflict (problem_code) do nothing;")
        c["problems"] += 1
        rc_codes = []
        for k, (rname, rcat, rexp, rw) in enumerate(rcs, 1):
            rcode = f"RC-{pfx}-3{n:02d}-{k}"
            rc_codes.append(rcode)
            out.append(f"insert into root_causes (root_cause_code, problem_id, root_cause_name,"
                       f" root_cause_category, explanation, confidence_weight, layer,"
                       f" primary_stage_group, industry_relevance) values ({q(rcode)}, {pref(pcode)},"
                       f" {q(rname)}, {q(rcat)}, {q(rexp)}, {rw}, 'internal', 'Stage 0→1',"
                       f" {j([icode])}) on conflict (root_cause_code) do nothing;")
            c["root_causes"] += 1
        for k, (steps, principles) in enumerate(ivs, 1):
            ic = f"INT-{pfx}-3{n:02d}-{k}"
            out.append(f"insert into interventions (intervention_code, problem_id, root_cause_ids,"
                       f" capability_domain, section, recommended_frameworks, immediate_next_steps,"
                       f" stage_relevance, industry_relevance, design_principles,"
                       f" secondary_root_cause_ids) values ({q(ic)}, {pref(pcode)}, {j(rc_codes)},"
                       f" {q(DOMAIN[pkey])}, {q(label + ' — ' + subcat)}, '[]'::jsonb, {j(steps)},"
                       f" {j([3,4,5])}, {j([icode])}, {j(principles)}, '[]'::jsonb)"
                       f" on conflict (intervention_code) do nothing;")
            c["interventions"] += 1
        for stage in STAGES:
            for k, (qtext, qtype, red, green) in enumerate(qs[stage], 1):
                qcode = f"{SPREFIX[stage]}-{pfx}-3{n:02d}-{k}"
                # EVIDENCE CONCENTRATION. Both questions in a stage point at the SAME
                # root cause, and which cause rotates by stage group.
                #
                # They used to rotate per question, so each cause collected one
                # question per stage. Measured: an E-Commerce founder was asked ten
                # batch questions, they mapped to TEN DISTINCT root causes with one
                # piece of evidence each, and not one of them reached the candidate
                # set -- ROOT_CAUSE_MAX_CANDIDATES is 8 and the original catalogue's
                # causes carry several questions apiece, so they filled every slot.
                # detection_score is the mean severity of a cause's negative
                # evidence, so a single answer cannot outrank three.
                #
                # Two per stage on one cause makes the new content competitive
                # without inventing evidence: the founder still answers the same
                # questions, they just accumulate against a cause instead of
                # scattering across three.
                rcode = rc_codes[(STAGES.index(stage)) % len(rc_codes)]
                out.append(f"insert into questions (question_code, category, question_text, problem_id,"
                           f" root_cause_id, question_type, difficulty_level, priority,"
                           f" is_distress_tagged, red_flag_pattern, green_flag_pattern,"
                           f" primary_stage_group, industry_relevance) values ({q(qcode)},"
                           f" {q(QCAT[pkey])}, {q(qtext)}, {pref(pcode)}, {rref(rcode)}, {q(qtype)},"
                           f" 2, 'CORE', false, {q(red)}, {q(green)}, {q(stage)}, {j([icode])})"
                           f" on conflict (question_code) do nothing;")
                c["questions"] += 1
                out.append(f"insert into question_industry_mapping (question_id, industry_code,"
                           f" stage_group, applicability_type) values ({qref(qcode)}, {q(icode)},"
                           f" {q(stage)}, 'primary')"
                           f" on conflict (question_id, industry_code, stage_group) do nothing;")
                c["mappings"] += 1

out += [
 "",
 "-- Self-check inside the transaction. If any count is short, this raises and the",
 "-- whole batch rolls back rather than leaving a partial load behind.",
 "do $$",
 "declare p int; r int; qn int; i int; m int;",
 "begin",
 "  select count(*) into p from problems where problem_code ~ '^(CEL|ECM|EDU|ENR|MED)-3[0-9][0-9]$';",
 "  select count(*) into r from root_causes where root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-3[0-9][0-9]-[0-9]$';",
 "  select count(*) into qn from questions where question_code ~ '^S(0|01|10)-(CEL|ECM|EDU|ENR|MED)-3[0-9][0-9]-[0-9]$';",
 "  select count(*) into i from interventions where intervention_code ~ '^INT-(CEL|ECM|EDU|ENR|MED)-3[0-9][0-9]-[0-9]$';",
 "  select count(*) into m from question_industry_mapping qim join questions qq on qq.question_id=qim.question_id",
 "    where qq.question_code ~ '^S(0|01|10)-(CEL|ECM|EDU|ENR|MED)-3[0-9][0-9]-[0-9]$';",
 "  if p <> 45 or r <> 135 or qn <> 270 or i <> 90 or m <> 270 then",
 "    raise exception 'batch 2 incomplete: problems=% root_causes=% questions=% interventions=% mappings=% (expected 45/135/270/90/270)', p, r, qn, i, m;",
 "  end if;",
 "  raise notice 'batch 2 ok: 45 problems, 135 root causes, 270 questions, 90 interventions, 270 mappings';",
 "end $$;",
 "",
 "COMMIT;",
]

path = os.path.join(B, "ally_batch2_PORTABLE_no_ids.sql")
open(path, "w").write("\n".join(out) + "\n")
print("written:", path)
print("rows:", c, "| total", sum(c.values()))
