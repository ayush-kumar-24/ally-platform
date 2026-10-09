"""Render the Entity Mapping & Domain Model document.

Textual, as asked. Where the ER document answers "what columns does this
table have", this one answers "what is this entity, who writes it, who reads
it, and which screen does it end up on".

Run:  python3 scripts/docs/render_mapping.py <schema.json> <usage.json> > Entity_Mapping.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import descriptions as D  # noqa: E402

PREV = {"tables": 47, "date": "July 2026"}

RLS = {"on": 40, "total": 104, "policies": 30, "tables_with_policy": 29,
       "deny_all": ["admin_audit_log", "alembic_version", "broadcasts",
                    "coupon_redemptions", "coupons", "feature_flags",
                    "model_task_routing", "notification_types",
                    "revoked_tokens", "support_bot_answers",
                    "support_bot_misses"]}

LIFECYCLE = [
    ("Sign-up", "The identity provider issues a token; the application stores "
     "only the link to it.", ["founders", "revoked_tokens"]),
    ("Consent", "Terms and privacy are accepted, and the diagnosis opt-in is "
     "taken separately. Both are recorded; the diagnosis gate reads the "
     "second one and fails closed when it is absent.",
     ["founder_consents", "consents", "consent_history"]),
    ("Onboarding", "Four sections write the profile: stage and experience, "
     "what the founder is building, what they know, where they are headed. "
     "Required fields differ by path and stage, and `profile_completed` is "
     "computed from that set rather than set by hand.",
     ["founders", "founder_context"]),
    ("Founder DNA", "Fifteen dimensions resolved from a narrative question "
     "bank. The diagnosis will not open until every one is resolved.",
     ["founder_dna_answers", "founders"], ["founder_dna_questions"]),
    ("Diagnosis", "A session is opened against the stage's question budget. "
     "Each question is chosen by the six scope axes and each answer is graded "
     "green, amber or red.",
     ["sessions", "answers", "session_context_facts"],
     ["questions", "question_industry_mapping", "founder_stages"]),
    ("Reasoning", "The graded session is scored per pillar, a stage is "
     "assessed, root causes are ranked and an archetype is resolved.",
     ["stage_assessments", "detected_root_causes"],
     ["archetypes", "root_causes", "root_cause_weights", "scoring_rules"]),
    ("Report", "Two reports are written from the same session: the "
     "founder-facing Clarity Report and the staff-only intelligence layer.",
     ["founder_reports", "internal_intelligence_reports", "report_shares"]),
    ("Acting on it", "The founder turns the report into plans, goals and "
     "daily actions, and Ally proposes suggestions against them.",
     ["planning_plans", "planning_goals", "planning_tasks", "daily_actions",
      "suggestions"], ["interventions", "frameworks"]),
    ("Withdrawal or deletion", "Restricting processing stops every route that "
     "would call an LLM. A deletion request runs a state machine from OTP "
     "through a grace period to execution.",
     ["privacy_requests", "data_deletion_requests", "founders"]),
]


def main() -> int:
    schema = json.load(open(sys.argv[1]))
    usage = json.load(open(sys.argv[2]))
    T = schema["tables"]
    blurbs = schema["part_blurbs"]
    by_part: dict[str, list[str]] = defaultdict(list)
    for name, t in T.items():
        by_part[t["part"]].append(name)

    o: list[str] = []
    w = o.append

    w("# Founder Alley — Database Entity Mapping and Domain Model")
    w("")
    w("**GoXL Consulting Solutions Pvt. Ltd.**  ")
    w("*Clarity Before Action*")
    w("")
    w("CONFIDENTIAL — INTERNAL USE ONLY")
    w("")
    w(f"Version 2 · {schema['totals']['tables']} tables · complete reference")
    w("")
    w("| | |")
    w("| --- | --- |")
    w(f"| **Schema revision** | `{schema['alembic_head']}` (Alembic head) |")
    w(f"| **Generated** | {schema['generated_at'][:19].replace('T', ' ')} |")
    w("| **Companion document** | Entity Relationship Diagram "
      "(`ER_Diagram.md`) — field-level detail for every table |")
    w(f"| **Supersedes** | Database Entity Mapping, {PREV['date']} "
      f"({PREV['tables']} tables) |")
    w("")
    w("This document is about **meaning**. For each entity: what it is, which "
      "part of the application writes it, which reads it, and which screen it "
      "reaches. The ER document is the field-level companion — types, keys "
      "and constraints live there and are not repeated here.")
    w("")

    # ---- what changed ---------------------------------------------------
    w("## What changed since the July 2026 version")
    w("")
    w(f"- **{PREV['tables']} tables became {schema['totals']['tables']}.** "
      "Whole domains are new: Founder DNA, planning and goals, vision, "
      "credits and coupons, feature flags, broadcasts, the launch state "
      "machine, the support bot, and the LLM call log.")
    w("- **The question bank grew from 208 rows to "
      f"{T['questions']['rows']:,}**, gained a fourth stage group (Exit) and "
      "six scope columns that decide which founders may be asked what.")
    w("- **A mandatory phase was added between onboarding and diagnosis.** "
      "Founder DNA resolves fifteen dimensions, and `POST /diagnosis/start` "
      "refuses until it is complete. Any description of the journey that goes "
      "straight from onboarding to diagnosis is now wrong.")
    w("- **The RLS position has changed and is no longer uniform.** The "
      "previous document stated RLS was enabled on all 47 tables. See the "
      "access section below, which reports what is actually true and where it "
      "differs by environment.")
    w("")

    # ---- the domain model -----------------------------------------------
    w("## The domain model")
    w("")
    w(f"The {schema['totals']['tables']} tables fall into "
      f"{len(by_part)} clusters. Read this as the shape of the system before "
      "the table-by-table detail.")
    w("")
    for part in sorted(by_part):
        title, blurb = blurbs[part]
        rows = sum(T[n]["rows"] for n in by_part[part])
        nt = len(by_part[part])
        w(f"**Part {part} — {title}** · {nt} "
          f"{'table' if nt == 1 else 'tables'} · "
          f"{rows:,} {'row' if rows == 1 else 'rows'}")
        w("")
        w(blurb)
        w("")
    w("Two relationships hold the whole thing together. **`founders` is the "
      "hub**: almost every founder-scoped table carries a `founder_id` and "
      "cascades from it, which is what makes a deletion request executable in "
      "the first place. **`sessions` is the second hub**: the diagnosis, its "
      "answers, its reasoning output and both reports all hang off one "
      "session row, so a session is the unit a diagnosis can be reasoned "
      "about, re-run or thrown away as a whole.")
    w("")

    # ---- lifecycle ------------------------------------------------------
    w("## The founder data lifecycle")
    w("")
    w("The path a founder's data actually travels, in order. Each step names "
      "the tables it writes.")
    w("")
    for i, step in enumerate(LIFECYCLE, 1):
        name, text, writes = step[0], step[1], step[2]
        reads = step[3] if len(step) > 3 else []
        w(f"**{i}. {name}** — {text}")
        w("")
        w("  Writes: " + ", ".join(f"`{t}`" for t in writes))
        if reads:
            w("")
            w("  Reads: " + ", ".join(f"`{t}`" for t in reads))
        w("")
    w("The order matters in two places that are enforced rather than "
      "conventional. Onboarding must complete before Founder DNA can start, "
      "and Founder DNA must complete before a diagnosis can start — five "
      "separate gates sit on `POST /diagnosis/start`: plan entitlement, "
      "profile completion, diagnosis consent, AI-processing permission, and "
      "Founder DNA completion.")
    w("")

    # ---- complete mapping -----------------------------------------------
    w("## Complete entity mapping")
    w("")
    w(f"All {schema['totals']['tables']} entities. **Owned by** is the "
      "application area that writes the table; **Reaches** is the screen or "
      "screens where it surfaces.")
    w("")
    w("| # | Entity | Part | Purpose | Owned by | Reaches |")
    w("| --: | --- | --- | --- | --- | --- |")
    n = 0
    for part in sorted(by_part):
        for name in sorted(by_part[part]):
            n += 1
            purpose = (D.TABLES.get(name) or "— not yet described —")
            short = purpose.split(". ")[0].rstrip(".")
            if len(short) > 85:
                short = short[:82] + "..."
            areas = usage["api_areas"][name] + usage["service_areas"][name]
            owned = ", ".join(f"`{a}`" for a in areas[:3]) or "—"
            if len(areas) > 3:
                owned += f" +{len(areas) - 3}"
            scr = usage["screens"][name]
            reach = ", ".join(scr[:3]) or "—"
            if len(scr) > 3:
                reach += f" +{len(scr) - 3}"
            w(f"| {n} | `{name}` | {part} | {short} | {owned} | {reach} |")
    w("")

    # ---- per-part detail ------------------------------------------------
    num = 0
    for part in sorted(by_part):
        title, blurb = blurbs[part]
        w("---")
        w("")
        w(f"## Part {part} — {title}")
        w("")
        w(blurb)
        w("")
        for name in sorted(by_part[part]):
            num += 1
            t = T[name]
            w(f"### {num}. `{name}`")
            w("")
            w(D.TABLES.get(name) or "— not yet described —")
            w("")
            parents = sorted({fk["ref_table"] for fk in t["fks"]})
            children = sorted({c for c in T
                               if any(fk["ref_table"] == name
                                      for fk in T[c]["fks"])})
            areas = usage["api_areas"][name] + usage["service_areas"][name]
            w("| | |")
            w("| --- | --- |")
            w(f"| Rows (local) | {t['rows']:,} |")
            w(f"| Columns | {len(t['columns'])} |")
            w("| ORM model | "
              + (f"`{usage['orm_classes'][name]}`" if name in usage["orm_classes"]
                 else "**none — raw SQL only**") + " |")
            w("| Written / read by | "
              + (", ".join(f"`{a}`" for a in areas) or "— no reference found —")
              + " |")
            w("| Reaches | "
              + (", ".join(usage["screens"][name]) or "— no screen —") + " |")
            w("| Depends on | "
              + (", ".join(f"`{p}`" for p in parents) or "— nothing —") + " |")
            w("| Depended on by | "
              + (", ".join(f"`{c}`" for c in children) or "— nothing —") + " |")
            w("")
            cols = D.COLUMNS.get(name)
            if cols:
                w("**Fields worth knowing**")
                w("")
                for cn, desc in cols.items():
                    w(f"- `{cn}` — {desc}")
                w("")

    # ---- access ---------------------------------------------------------
    w("---")
    w("")
    w("## Access and Row Level Security")
    w("")
    w("The previous version of this document stated that RLS was enabled on "
      "all 47 tables. That is no longer the position, and the position now "
      "**differs by environment** — so this section reports what was measured, "
      "where, rather than a single claim.")
    w("")
    w(f"Measured on the local database at `{schema['alembic_head']}`:")
    w("")
    w("| | Count |")
    w("| --- | --: |")
    w(f"| Tables with RLS enabled | {RLS['on']} of {RLS['total']} |")
    w(f"| Policies defined | {RLS['policies']} across "
      f"{RLS['tables_with_policy']} tables |")
    w(f"| **RLS enabled with no policy (deny-all)** | {len(RLS['deny_all'])} |")
    w("")
    w("### The deny-all tables, and why they are probably not a bug")
    w("")
    w("These eleven have RLS switched on and no policy, which in Postgres "
      "means deny by default — every `SELECT` returns zero rows and every "
      "write fails:")
    w("")
    w(", ".join(f"`{t}`" for t in RLS["deny_all"]))
    w("")
    w("**This is a local artefact, not a production finding.** Several "
      "migrations create their policies conditionally, because "
      "`CREATE POLICY ... TO <role>` errors when the role does not exist, "
      "while `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` is unconditional. "
      "None of `ally_app`, `authenticated`, `anon` or `service_role` exists "
      "in this database, so the policies were skipped and the enable was not. "
      "Migration `a2d5f74c8e13` documents this exact mechanism, which caused "
      "a production sign-up outage on `waitlist_registrations` and was fixed "
      "by creating those policies `FOR PUBLIC` instead.")
    w("")
    w("**It does mean RLS cannot be verified from this database.** Two things "
      "follow. Production has the roles, so its policies will have been "
      "created — but that should be confirmed, not assumed. And the Supabase "
      "database shows the *opposite* problem: six tables there have RLS "
      "**disabled** entirely (`support_bot_answers`, `support_bot_misses`, "
      "`coupons`, `coupon_redemptions`, `notification_types`, "
      "`_perf_baseline`), which Supabase itself flags as critical because "
      "anyone holding the anon key can read or write every row. Enabling RLS "
      "on them without writing policies first would reproduce the outage "
      "above, so each needs a policy designed before the switch is thrown.")
    w("")
    w("### The founder-scoping pattern")
    w("")
    w("Where policies do exist, most follow one shape: the row is visible "
      "when its `founder_id` matches the caller's, resolved through a helper "
      "function rather than repeated in each policy. Three groups sit outside "
      "that pattern:")
    w("")
    w("- **Staff-only, no founder-facing policy** — `admin_notes`, "
      "`admin_audit_log`, `internal_intelligence_reports`, `webhook_logs`, "
      "`llm_call_log`. A founder cannot read these by any route.")
    w("- **Read-only for the founder** — `detected_root_causes` and the other "
      "reasoning outputs. A founder may see their diagnosis results and "
      "cannot alter them.")
    w("- **Reference data** — everything in Part A. Read-only for everyone "
      "at runtime; written only by migrations.")
    w("")

    # ---- appendix: method ----------------------------------------------
    w("## Appendix A — How the mapping was derived, and where it is weak")
    w("")
    w("The **Owned by** and **Reaches** columns are derived from the source "
      f"by `scripts/docs/extract_usage.py`, over {usage['files_scanned']} "
      "Python files. A table is reported as used by an area only because the "
      "source shows it: either the table name in SQL context (after `FROM`, "
      "`JOIN`, `INTO`, `UPDATE`, `DELETE FROM`, or in a `__tablename__`), or "
      "the name of the ORM class bound to it.")
    w("")
    w("**Why not a simple name search.** The first version of this script "
      "searched for the table's name as a whole word, and the result was "
      "unusable: `answers` matched `api/payments`, `sessions` matched "
      "`api/auth` — which is auth sessions, an unrelated thing — and "
      "`questions`, `problems`, `messages` and `notifications` matched much "
      "of the codebase, because they are ordinary English words that appear "
      "in comments. It also under-matched: `planning_tasks` came back touched "
      "by nothing, because that module refers to it only through its ORM "
      "class. A keyword screen was wrong in both directions at once, which is "
      "the same lesson the question bank taught three times.")
    w("")
    w("**Two weaknesses remain, stated rather than hidden.** A table reached "
      "by some third route — dynamic SQL, a name built at runtime — is "
      "missed. And **Reaches** lists screens whose area touches the table at "
      "all, including indirectly: `planning_tasks` lists `/privacy` because "
      "the deletion executor must clear it, not because anything is displayed "
      "there. Treat the column as *where this data is involved*, not *where "
      "it is shown*.")
    w("")
    nr = usage["no_reference"]
    w(f"**{len(nr)} tables matched nothing at all**: "
      + ", ".join(f"`{t}`" for t in nr) + ". Of those, `alembic_version` is "
      "Alembic's own, `founder_dimensions` and `founder_dimension_profile` "
      "are superseded, and `session_context_facts` and `support_bot_answers` "
      "are reached in ways this method does not see — both are live.")
    w("")
    w("## Appendix B — Entities with no ORM model")
    w("")
    w(f"{usage['orm_coverage']['total'] - usage['orm_coverage']['with_model']} "
      f"of {usage['orm_coverage']['total']} tables have no SQLAlchemy model "
      "and are reached only by raw SQL. Listed in the ER document's Appendix "
      "B. The one to look at first is `question_industry_mapping`: "
      f"{T['question_industry_mapping']['rows']:,} rows, core to industry "
      "question selection, and no model to type-check a change against.")
    w("")

    print("\n".join(o))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
