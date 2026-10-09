"""Dump the live schema to JSON, as the source for the ER and Entity Mapping docs.

WHY THE DATABASE AND NOT THE ORM. There is no single metadata object that
covers this schema. Measured on 2026-10-09 against head b6e82f4d13a7:

    81 of 104 tables have a SQLAlchemy model, spread across 18 modules
    (app/models/*.py plus a db_models.py inside eight feature packages,
    all sharing the one Base in app/db/session.py)
    23 tables have no model at all and are reached only by raw SQL

So importing `app.models.schema` alone sees 69 tables, importing every model
module sees 81, and neither is the schema. The migrated database is, which is
what this reads. The ORM is used only to enrich descriptions, never as the
list of what exists -- a table nobody wrote a model for is still a table the
documents have to describe.

Run:  python3 scripts/docs/extract_schema.py > /path/to/schema.json
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import psycopg

DSN = os.environ.get(
    "DOCS_DSN", "postgresql://postgres:postgres@127.0.0.1:5432/ally"
)

# Every table is assigned to exactly one part. The parts, and their order,
# follow the July 2026 documents so the two read as successors rather than
# replacements; the parts after I are new because the tables are.
#
# UNASSIGNED MUST COME BACK EMPTY. A table added to the database and not added
# here is a table the documents would silently omit, which is the specific way
# the previous version went stale -- it described 47 tables of a schema that
# had grown past it. The generator fails instead.
PARTS: dict[str, tuple[str, str]] = {}


def _part(key: str, title: str, blurb: str, tables: list[str]) -> None:
    for t in tables:
        if t in PARTS:
            raise SystemExit(f"table {t!r} assigned to two parts")
        PARTS[t] = (key, title)
    _PART_BLURB[key] = (title, blurb)


_PART_BLURB: dict[str, tuple[str, str]] = {}

_part("A", "Pre-filled Intelligence",
      "Populated before any founder signs up. Read-only during a live session. "
      "This is the content the engine reasons over -- the question bank, the "
      "problem and root-cause library, the industry and scoring reference data.",
      ["founder_stages", "readiness_pillars", "problems", "problem_stage_mapping",
       "root_causes", "root_cause_weights", "questions", "question_tags",
       "question_tag_mapping", "question_industry_mapping", "behaviour_patterns",
       "blind_spots", "industries", "industry_stage_thresholds",
       "agent_interpretations", "scoring_rules", "interventions", "frameworks",
       "archetypes", "prompt_library", "psychological_state_signals",
       "session_state_bands", "chronic_state_inference", "stage_diagnosis_logic",
       "visual_question_bank", "founder_dna_questions", "current_problem_questions",
       "founder_dimensions", "business_dimensions", "model_task_routing",
       "notification_types", "support_bot_answers"])

_part("B", "Authentication",
      "Identity. Managed by the configured auth provider; the application "
      "stores only the link to it.",
      ["revoked_tokens"])

_part("C", "Profile and Onboarding",
      "Who the founder is and what they told us before any diagnosis ran. "
      "Every later phase reads from here.",
      ["founders", "founder_context", "founder_settings", "founder_memory",
       "founder_memory_events", "founder_dimension_profile"])

_part("D", "Chat and Conversation",
      "Ally Chat: the conversation container, the messages in it, and the "
      "token accounting that bounds it.",
      ["conversations", "messages", "user_token_usage", "file_uploads",
       "daily_token_usage"])

_part("E", "Retrieval (RAG)",
      "The document corpus Ally retrieves from, its chunk-level embeddings, "
      "and the retrieval audit trail.",
      ["rag_documents", "rag_chunks", "rag_retrieval_log"])

_part("F", "Consent and Data Protection (DPDP)",
      "What the founder agreed to, when, and the machinery that honours a "
      "withdrawal or a deletion request.",
      ["consents", "consent_history", "founder_consents", "cookie_preferences",
       "privacy_requests", "data_deletion_requests", "audit_logs"])

_part("G", "Platform",
      "Notifications, commerce and scheduling -- everything around the "
      "product rather than inside it.",
      ["notifications", "subscriptions", "payments", "discovery_calls",
       "report_shares", "coupons", "coupon_redemptions", "credit_transactions",
       "plan_call_usage", "unbilled_usage", "calendar_connections",
       "feature_flags", "feature_flag_overrides", "broadcasts", "broadcast_reads",
       "launch_state", "direct_signup_capacity", "gateway_plans",
       "waitlist_registrations", "waitlist_slot_openings"])

_part("H", "Admin and Operations",
      "Staff-facing records and the operational telemetry behind the admin "
      "panel. Not founder-readable.",
      ["admin_notes", "admin_audit_log", "analytics_events", "webhook_logs",
       "llm_call_log", "support_bot_misses", "founder_feedback"])

_part("I", "Diagnosis Engine",
      "The live session and everything it produces. This is the USP: the "
      "session state, every graded answer, the reasoning output and the two "
      "reports built from it.",
      ["sessions", "answers", "session_context_facts", "stage_assessments",
       "detected_root_causes", "founder_reports", "internal_intelligence_reports",
       "founder_dna_answers", "current_problem_answers", "founder_visual_choices"])

_part("J", "Planning, Goals and Vision",
      "What the founder does with the report: plans, goals, tasks, reminders "
      "and the longer-range vision work.",
      ["planning_plans", "planning_goals", "planning_tasks", "planning_reminders",
       "daily_actions", "founder_goals", "achievements", "vision_territories",
       "vision_summary", "framework_usage", "founder_daily_quotes",
       "suggestions", "suggestion_feedback"])

_part("K", "Schema Management",
      "Not application data. Listed for completeness because it exists in "
      "every environment and is the first thing to check when two databases "
      "disagree.",
      ["alembic_version"])


SQL_TABLES = """
select c.relname as tbl,
       coalesce(obj_description(c.oid), '') as tbl_comment,
       c.reltuples::bigint as approx_rows
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r','p')
order by c.relname
"""

SQL_COLS = """
select table_name, column_name, ordinal_position, data_type,
       character_maximum_length, numeric_precision, numeric_scale,
       is_nullable, column_default,
       coalesce(col_description(
           format('public.%I', table_name)::regclass::oid, ordinal_position), '') as comment
from information_schema.columns
where table_schema = 'public'
order by table_name, ordinal_position
"""

SQL_CONSTRAINTS = """
select rel.relname as tbl, con.conname, con.contype,
       pg_get_constraintdef(con.oid) as def,
       array_remove(array_agg(att.attname order by u.ord), null) as cols,
       coalesce(fref.relname, '') as ref_table
from pg_constraint con
join pg_class rel on rel.oid = con.conrelid
join pg_namespace n on n.oid = rel.relnamespace
left join unnest(con.conkey) with ordinality as u(attnum, ord) on true
left join pg_attribute att on att.attrelid = rel.oid and att.attnum = u.attnum
left join pg_class fref on fref.oid = con.confrelid
where n.nspname = 'public' and con.contype in ('p','f','u','c')
group by rel.relname, con.conname, con.contype, con.oid, fref.relname
order by rel.relname, con.contype
"""


def _render_type(r: dict) -> str:
    t = r["data_type"]
    if r["character_maximum_length"]:
        return f"VARCHAR({r['character_maximum_length']})"
    if t == "numeric" and r["numeric_precision"]:
        return f"DECIMAL({r['numeric_precision']},{r['numeric_scale']})"
    return {
        "timestamp with time zone": "TIMESTAMPTZ",
        "timestamp without time zone": "TIMESTAMP",
        "character varying": "VARCHAR",
        "double precision": "DOUBLE",
        "integer": "INTEGER",
        "bigint": "BIGINT",
        "smallint": "SMALLINT",
        "boolean": "BOOLEAN",
        "text": "TEXT",
        "jsonb": "JSONB",
        "json": "JSON",
        "uuid": "UUID",
        "date": "DATE",
        "ARRAY": "ARRAY",
        "USER-DEFINED": "USER-DEFINED",
    }.get(t, t.upper())


def main() -> int:
    conn = psycopg.connect(DSN, row_factory=psycopg.rows.dict_row)

    tables = {r["tbl"]: {"name": r["tbl"], "comment": r["tbl_comment"],
                         "approx_rows": r["approx_rows"], "columns": [],
                         "pk": [], "fks": [], "uniques": [], "checks": []}
              for r in conn.execute(SQL_TABLES)}

    # Exact counts -- reltuples is an estimate and this document is a reference.
    for name in tables:
        n = conn.execute(f'select count(*) as c from public."{name}"').fetchone()["c"]
        tables[name]["rows"] = n

    for r in conn.execute(SQL_COLS):
        if r["table_name"] not in tables:
            continue
        tables[r["table_name"]]["columns"].append({
            "name": r["column_name"],
            "type": _render_type(r),
            "nullable": r["is_nullable"] == "YES",
            "default": r["column_default"],
            "comment": r["comment"],
        })

    for r in conn.execute(SQL_CONSTRAINTS):
        t = tables.get(r["tbl"])
        if not t:
            continue
        if r["contype"] == "p":
            t["pk"] = list(r["cols"])
        elif r["contype"] == "f":
            t["fks"].append({"name": r["conname"], "cols": list(r["cols"]),
                             "ref_table": r["ref_table"], "def": r["def"]})
        elif r["contype"] == "u":
            t["uniques"].append({"name": r["conname"], "cols": list(r["cols"])})
        elif r["contype"] == "c":
            t["checks"].append({"name": r["conname"], "def": r["def"]})

    unassigned = sorted(set(tables) - set(PARTS))
    orphan_parts = sorted(set(PARTS) - set(tables))

    for name, t in tables.items():
        t["part"] = PARTS.get(name, ("?", "UNASSIGNED"))[0]

    out = {
        "generated_at": conn.execute("select now() as n").fetchone()["n"].isoformat(),
        "alembic_head": conn.execute(
            "select version_num from alembic_version").fetchone()["version_num"],
        "part_blurbs": _PART_BLURB,
        "totals": {
            "tables": len(tables),
            "columns": sum(len(t["columns"]) for t in tables.values()),
            "foreign_keys": sum(len(t["fks"]) for t in tables.values()),
            "rows": sum(t["rows"] for t in tables.values()),
        },
        "unassigned": unassigned,
        "orphan_parts": orphan_parts,
        "tables": tables,
    }
    json.dump(out, sys.stdout, indent=1, default=str)

    if unassigned or orphan_parts:
        print(f"\n\nUNASSIGNED TABLES: {unassigned}", file=sys.stderr)
        print(f"PARTS NAMING MISSING TABLES: {orphan_parts}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
