"""Work out, for every table, which parts of the application touch it.

This is the evidence behind the Entity Mapping document's table -> API ->
screen column. It is derived from the source, not asserted by hand.

HOW IT MATCHES, AND WHY NOT BY NAME ALONE. The first version of this script
searched each module for the table's name as a whole word. That over-matched
so badly it was useless: `answers` matched `api/payments`, `sessions` matched
`api/auth` (auth sessions, a different thing entirely), and anything called
`questions`, `problems`, `notifications` or `messages` matched half the
codebase, because those are ordinary English words that appear in comments and
variable names. It also under-matched -- `planning_tasks` came back touched by
nothing, because that module only ever refers to it through its ORM class.

The same lesson the question bank taught three times over: a keyword screen is
wrong in both directions at once. So this matches two precise things instead:

  1. SQL context -- the name after FROM / JOIN / INTO / UPDATE / DELETE FROM,
     or in a __tablename__ assignment.
  2. The ORM class bound to that table, by class name, for the 81 tables that
     have one.

A table reached some third way is still missed, so the document reports what
this found as evidence of use rather than as a complete census.

Run:  python3 scripts/docs/extract_usage.py <schema.json> > usage.json
"""
from __future__ import annotations

import importlib
import json
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"
# Running this as a script puts scripts/docs on sys.path, not the backend
# root, so `import app` fails without this.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

MODEL_MODULES = [
    "app.models.schema", "app.models.auth", "app.models.diagnosis",
    "app.models.llm", "app.models.memory", "app.models.partitioned",
    "app.models.reasoning", "app.models.scoring", "app.models.suggestions",
    "app.models.waitlist", "app.achievements.db_models",
    "app.calendar_sync.db_models", "app.consents.db_models",
    "app.credits.db_models", "app.founder_goals.db_models",
    "app.framework_usage.db_models", "app.planning.db_models",
    "app.vision.db_models",
]

#: Router area -> the frontend routes that call it. Hand-maintained, because
#: nothing in the source states it: a page calls a service function which
#: builds a URL. Checked against frontend/src/services/*.js and the route
#: table in frontend/src/App.jsx.
API_TO_SCREEN = {
    "diagnosis": ["/app/diagnosis", "/app/thinking"],
    "founder_dna": ["/app/founder-dna", "/app/founder-dna-journey"],
    "current_problem": ["/app/current-problem"],
    "reports": ["/app/report", "/app/business-dna"],
    "reasoning": ["(server-side, feeds /app/report)"],
    "profile": ["/guided/profile", "/guided/summary", "/guided/validate",
                "/app/profile"],
    "consents": ["/guided/welcome", "/app/profile"],
    "privacy": ["/app/profile", "/privacy"],
    "chat": ["/app/ally-chat"],
    "planning": ["/app/next-steps", "/app/goals"],
    "founder_goals": ["/app/goals"],
    "vision": ["/app/vision"],
    "achievements": ["/app/achievements"],
    "framework_usage": ["/app/frameworks"],
    "knowledge": ["/app/knowledge/:section"],
    "plans": ["/app/plan", "/app/billing"],
    "payments": ["/app/billing"],
    "discovery": ["/app/discovery-call"],
    "feedback": ["/app/feedback"],
    "support": ["/app/help"],
    "dashboard": ["/app/journey"],
    "notifications": ["/app (global)"],
    "quotes": ["/app/journey"],
    "settings": ["/app/profile"],
    "intelligence": ["(staff only)"],
    "admin": ["/admin/*"],
    "auth": ["/guided/login", "/guided/resume"],
    "reference": ["/guided/profile"],
    "calendar": ["/app/discovery-call"],
    "impression": ["/guided/expectation"],
    "launch": ["/", "/admin/launch"],
    "waitlist": ["/", "/admin/waitlist"],
    "voice": ["/app/ally-chat", "/app/diagnosis"],
    "webhooks": ["(inbound, no screen)"],
    # Service packages. Many tables are owned by app/<feature>/ and only
    # reached through a router that delegates, so attributing screens from
    # api/* areas alone left 59 tables with no screen at all.
    "coupons": ["/app/billing", "/admin/coupons"],
    "credits": ["/app/billing", "/admin/users/:id"],
    "planning": ["/app/next-steps", "/app/goals"],
    "vision": ["/app/vision"],
    "achievements": ["/app/achievements"],
    "consents": ["/guided/welcome", "/app/profile"],
    "privacy": ["/app/profile", "/privacy", "/admin/privacy"],
    "admin": ["/admin/*"],
    "notifications": ["/app (global)"],
    "support_bot": ["/app/help", "/admin/*"],
    "launch": ["/", "/admin/launch"],
    "jobs": ["(background, no screen)"],
    "emails": ["(background, no screen)"],
    "learning": ["(background, no screen)"],
    "eval": ["(offline, no screen)"],
    "integrations": ["(server-side)"],
    "calendar_sync": ["/app/discovery-call"],
    "framework_usage": ["/app/frameworks"],
    "founder_goals": ["/app/goals"],
    "ai_chat": ["/app/ally-chat"],
    "plans": ["/app/plan", "/app/billing"],
    "payments": ["/app/billing"],
    "settings": ["/app/profile"],
}


def orm_classes() -> dict[str, str]:
    """table name -> ORM class name, for the tables that have a model."""
    warnings.filterwarnings("ignore")
    for m in MODEL_MODULES:
        try:
            importlib.import_module(m)
        except Exception:
            pass
    from app.db.session import Base
    out = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        tbl = getattr(cls, "__tablename__", None)
        if tbl:
            out[tbl] = cls.__name__
    return out


def area_of(path: Path) -> str:
    rel = path.relative_to(APP).as_posix().split("/")
    if rel[0] == "api" and len(rel) > 3:
        return f"api/{rel[2]}"
    if rel[0] == "api" and len(rel) > 2:
        return f"api/{rel[1]}"
    return rel[0]


def main() -> int:
    schema = json.load(open(sys.argv[1]))
    tables = sorted(schema["tables"])
    classes = orm_classes()

    files = [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]
    sources = {p: p.read_text(errors="replace") for p in files}

    sql_pat = {
        t: re.compile(
            rf"(?:from|join|into|update|delete\s+from|__tablename__\s*=\s*['\"])"
            rf"\s*[\"'`]?(?:public\.)?{re.escape(t)}(?![A-Za-z0-9_])",
            re.IGNORECASE)
        for t in tables
    }
    cls_pat = {
        t: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(c)}(?![A-Za-z0-9_])")
        for t, c in classes.items()
    }

    used_by: dict[str, set[str]] = defaultdict(set)
    how: dict[str, set[str]] = defaultdict(set)
    for path, src in sources.items():
        area = area_of(path)
        for t in tables:
            if sql_pat[t].search(src):
                used_by[t].add(area)
                how[t].add("sql")
            if t in cls_pat and cls_pat[t].search(src):
                used_by[t].add(area)
                how[t].add("orm")

    api_areas = {t: sorted(a for a in used_by[t] if a.startswith("api/"))
                 for t in tables}
    service_areas = {t: sorted(a for a in used_by[t] if not a.startswith("api/"))
                     for t in tables}

    screens = {}
    for t in tables:
        s: list[str] = []
        for a in api_areas[t] + service_areas[t]:
            key = a.split("/", 1)[1] if a.startswith("api/") else a
            for scr in API_TO_SCREEN.get(key, []):
                if scr not in s:
                    s.append(scr)
        screens[t] = s

    out = {
        "files_scanned": len(files),
        "orm_coverage": {"with_model": len(classes), "total": len(tables)},
        "orm_classes": classes,
        "used_by": {t: sorted(used_by[t]) for t in tables},
        "match_kind": {t: sorted(how[t]) for t in tables},
        "api_areas": api_areas,
        "service_areas": service_areas,
        "screens": screens,
        "no_reference": sorted(t for t in tables if not used_by[t]),
        "no_api": sorted(t for t in tables if not api_areas[t]),
    }
    json.dump(out, sys.stdout, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
