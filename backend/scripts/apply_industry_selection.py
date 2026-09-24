"""One-off: everything the industry-adaptive selection needs, in one command.

WHY A SCRIPT AND NOT `alembic upgrade head`. One blocker, and it is scoped to
the TEST database, not production.

The Supabase instance carries an ORPHANED STAMP in alembic_version --
f8a3c26e4b91, a revision that exists in no file in this repository -- so alembic
refuses to start from it there, and it is genuinely behind besides (the head
migration's RLS work is absent). Already documented in
scripts/_apply_dimension_code_column.py, which hit the same wall.

PRODUCTION IS FINE. RDS has a valid stamp: backend-deploy.yml runs
`alembic upgrade head` on every deploy and hard-fails on a non-zero exit, and it
has been succeeding. On RDS this script is the no-op that migration would have
made anyway, which is why every statement is idempotent.

An earlier version of this docstring also claimed "the migration graph has TEN
HEADS". THAT WAS WRONG -- it came from a hand-rolled parser that missed merge
revisions and saw 91 of the real 130. Alembic reports exactly ONE head,
c9f41b8e3a07. Corrected rather than deleted, because the claim was handed to the
AWS team.

This script does not touch `alembic_version`. Reconciling Supabase's stamp needs
an audit of which migrations actually ran there, not a blind `alembic stamp
head`, and that is separate from a schema fix.

WHY A SCRIPT AND NOT `psql -f data/rds/00*.sql`. The SQL files say the same
thing and are the right artifact to hand someone. But the production container
may not carry psql, and either way the files only reach the image on a deploy --
by which point running a module is simpler than locating a file inside it. Same
command shape DEPLOY.md already uses for every other one-off.

WHAT IT DOES, all additive and all idempotent:

  1. question_industry_mapping   the table the whole feature reads
  2. session_context_facts       session-scoped "this does not apply to me"
  3. question_tags.precondition_token
  4. fills the mapping from questions.industry_relevance  (expect 1,800 rows)
  5. fills top_pain_point_weights for the 26 industries that shipped without
  6. verifies, and FAILS LOUDLY if the numbers are wrong

WHAT BREAKS WITHOUT IT. The selection code fails OPEN by design, so a database
missing question_industry_mapping disables the whole industry feature silently:
no error, no startup warning, no wrong answer. It simply behaves as it did
before the feature was written, and the 1,800 industry questions stay eligible
for every founder -- 435 / 580 / 725 of another industry's questions per
founder, at Stage 0 / 0->1 / 1->10+ respectively.

Usage -- dry run first, it is the default:

    python -m scripts.apply_industry_selection
    python -m scripts.apply_industry_selection --confirm-writes

Reads DATABASE_URL from the environment when --database-url is not given, so on
ECS it needs no arguments and no credentials of your own:

    aws ecs run-task --region ap-south-1 \
      --cluster ally-backend-cluster --task-definition ally_backend_task:<rev> \
      --launch-type FARGATE --count 1 \
      --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=ENABLED}" \
      --overrides '{"containerOverrides":[{"name":"Main","command":[
         "python","-m","scripts.apply_industry_selection","--confirm-writes"]}]}'
"""

from __future__ import annotations

import argparse
import os
import sys

import sqlalchemy as sa

# --- expected end state, asserted rather than assumed -----------------------
EXPECTED_MAPPING_ROWS = 1800
EXPECTED_INDUSTRIES = 30
EXPECTED_PER_INDUSTRY = 60
EXPECTED_WEIGHT_ENTRIES = 240

_DDL = """
CREATE TABLE IF NOT EXISTS question_industry_mapping (
    id                 SERIAL      PRIMARY KEY,
    question_id        INTEGER     NOT NULL REFERENCES questions(question_id),
    industry_code      VARCHAR     NOT NULL REFERENCES industries(industry_code),
    stage_group        VARCHAR     NOT NULL,
    applicability_type VARCHAR     NOT NULL
        CHECK (applicability_type IN ('primary', 'supporting')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (question_id, industry_code, stage_group)
);
COMMENT ON TABLE question_industry_mapping IS
'Links a question to a specific industry + stage. A question with no row here is treated as universal (applies everywhere). applicability_type: primary = this is a defining question for this industry, supporting = relevant but not core.';
CREATE INDEX IF NOT EXISTS idx_qim_industry_stage
    ON question_industry_mapping (industry_code, stage_group);
CREATE INDEX IF NOT EXISTS idx_qim_question
    ON question_industry_mapping (question_id);

CREATE TABLE IF NOT EXISTS session_context_facts (
    id                     SERIAL      PRIMARY KEY,
    session_id             VARCHAR     NOT NULL,
    token                  VARCHAR     NOT NULL,
    value                  VARCHAR     NOT NULL,
    learned_from_answer_id INTEGER,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE session_context_facts IS
'Things learned about a founder DURING the current session only (e.g. they said a team question does not apply). This must never be written back into the founders table -- it only affects question selection for the rest of THIS session.';
CREATE INDEX IF NOT EXISTS idx_session_context_facts_session
    ON session_context_facts (session_id);

ALTER TABLE question_tags
    ADD COLUMN IF NOT EXISTS precondition_token VARCHAR DEFAULT NULL;
COMMENT ON COLUMN question_tags.precondition_token IS
'Nullable. If set (e.g. has_team, fundraising_intent), a question with this tag should only be shown when that condition is known to be true. NULL means no precondition -- do not set this on every tag automatically, only where genuinely required.';
"""

# --- row-level security ----------------------------------------------------
#
# NOT part of _DDL, and that is the whole point. An earlier version of this
# script enabled RLS unconditionally, justified as "a no-op, there is no
# PostgREST in front of RDS". That reasoning was WRONG and would have broken
# production: what makes RLS harmless is the CONNECTING ROLE, not the API in
# front of the database.
#
#     Supabase   tables owned by postgres; the app connects as postgres,
#                which has rolbypassrls = true  -> RLS never applies
#     RDS        the app connects as ally_app, which does NOT own these
#                tables, has no BYPASSRLS, and there are no policies
#                -> RLS ON means ally_app reads ZERO rows
#
# Zero rows is the exact silent failure this feature exists to avoid: selection
# fails open, so it would not error, it would quietly stop gating industries --
# indistinguishable from the table being missing.
#
# So the decision is made from the database, not from a comment. RLS is enabled
# only where it provably cannot lock the caller out.
_CAN_SAFELY_ENABLE_RLS = """
SELECT COALESCE(
    (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user), false)
 OR (SELECT pg_get_userbyid(relowner) = current_user
       FROM pg_class WHERE relname = 'question_industry_mapping')
"""

_ENABLE_RLS = (
    "ALTER TABLE question_industry_mapping ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE session_context_facts     ENABLE ROW LEVEL SECURITY",
)

# Derived from questions.industry_relevance, never from a literal list of ids:
# ids are surrogate keys that differ between instances, so a literal list would
# be wrong on every database but the one it was generated from. The seed
# migrations wrote industry_relevance themselves, which makes it the
# authoritative statement of which question belongs to which industry.
# '["all"]' is the default on every generic question and is excluded -- those
# are the universal ones that must keep reaching everyone.
_FILL_MAPPING = """
INSERT INTO question_industry_mapping
    (question_id, industry_code, stage_group, applicability_type)
SELECT q.question_id,
       jsonb_array_elements_text(q.industry_relevance),
       q.primary_stage_group,
       'primary'
FROM questions q
WHERE q.industry_relevance IS NOT NULL
  AND q.industry_relevance <> '["all"]'::jsonb
  AND q.primary_stage_group IS NOT NULL
ON CONFLICT (question_id, industry_code, stage_group) DO NOTHING
"""

#: The 26 industries that shipped with the '{}' default. saas, services,
#: manufacturing and ngo already carry weights and are deliberately absent.
#:
#: Same shape as those four: 8 codes, values only from 1.05/1.15/1.3/1.5 with
#: two at each level, spread over at least three pillars. 1.3 is the threshold
#: `industry_scope.normalise_weight` treats as strong.
#:
#: Reasoned from each industry's documented failure modes, not measured from
#: founder outcomes. Data, not behaviour -- an UPDATE changes them with no
#: deploy. A wrong weight costs question ORDER, never eligibility.
_WEIGHTS: dict[str, str] = {
    "adtech_marketing":     '{"SAL-005":1.5,"CMA-020":1.5,"GTM-007":1.3,"PRD-005":1.3,"SAL-003":1.15,"OPS-002":1.15,"TM-004":1.05,"MEX-001":1.05}',
    "agritech":             '{"IVA-001":1.5,"GTM-003":1.5,"FIN-001":1.3,"SAL-004":1.3,"TCI-001":1.15,"OPS-001":1.15,"RSK-002":1.05,"PSY-007":1.05}',
    "automotive":           '{"BMD-001":1.5,"OPS-003":1.5,"RSK-003":1.3,"OPS-006":1.3,"FIN-001":1.15,"SAL-003":1.15,"OPS-001":1.05,"CMA-001":1.05}',
    "beauty_personal_care": '{"GTM-007":1.5,"CMA-020":1.5,"SAL-003":1.3,"GTM-002":1.3,"SCL-039":1.15,"PRD-004":1.15,"OPS-004":1.05,"MEX-001":1.05}',
    "cleantech_energy":     '{"FIN-001":1.5,"SAL-002":1.5,"RSK-003":1.3,"OPS-006":1.3,"BMD-001":1.15,"GTM-005":1.15,"BPL-003":1.05,"OPS-001":1.05}',
    "consumer_electronics": '{"RSK-003":1.5,"PRD-004":1.5,"BMD-001":1.3,"OPS-003":1.3,"FIN-001":1.15,"SAL-003":1.15,"OPS-001":1.05,"CMA-002":1.05}',
    "ecommerce_d2c":        '{"GTM-007":1.5,"SAL-003":1.5,"SCL-039":1.3,"CMA-020":1.3,"FIN-001":1.15,"OPS-004":1.15,"PRD-004":1.05,"GTM-002":1.05}',
    "edtech":               '{"GTM-007":1.5,"IVA-001":1.5,"SAL-005":1.3,"PRD-002":1.3,"SAL-003":1.15,"TCI-002":1.15,"MEX-001":1.05,"OPS-005":1.05}',
    "fashion_apparel":      '{"BMD-001":1.5,"GTM-007":1.5,"CMA-020":1.3,"FIN-001":1.3,"PRD-004":1.15,"SCL-039":1.15,"OPS-004":1.05,"MEX-001":1.05}',
    "fintech":              '{"OPS-006":1.5,"RSK-016":1.5,"RSK-002":1.3,"SAL-004":1.3,"OPS-005":1.15,"BMD-001":1.15,"TM-005":1.05,"GTM-002":1.05}',
    "foodtech":             '{"BMD-001":1.5,"GTM-007":1.5,"OPS-001":1.3,"SCL-039":1.3,"FIN-001":1.15,"PRD-004":1.15,"OPS-006":1.05,"CMA-002":1.05}',
    "gaming":               '{"SAL-004":1.5,"GTM-007":1.5,"RSK-003":1.3,"SCL-039":1.3,"PRD-002":1.15,"IVA-001":1.15,"PRD-004":1.05,"TM-002":1.05}',
    "healthtech":           '{"IVA-001":1.5,"OPS-006":1.5,"SAL-004":1.3,"RSK-016":1.3,"TCI-001":1.15,"SAL-002":1.15,"PRD-004":1.05,"OPS-005":1.05}',
    "hrtech":               '{"GTM-002":1.5,"SAL-005":1.5,"SAL-002":1.3,"IVA-001":1.3,"GTM-007":1.15,"SAL-003":1.15,"PRD-001":1.05,"TCI-002":1.05}',
    "legaltech":            '{"IVA-001":1.5,"SAL-004":1.5,"SAL-002":1.3,"RSK-016":1.3,"GTM-002":1.15,"SAL-005":1.15,"PRD-004":1.05,"OPS-001":1.05}',
    "logistics":            '{"BMD-001":1.5,"OPS-001":1.5,"RSK-003":1.3,"SAL-003":1.3,"OPS-005":1.15,"TM-004":1.15,"OPS-006":1.05,"FIN-001":1.05}',
    "media_entertainment":  '{"SAL-004":1.5,"SCL-039":1.5,"GTM-007":1.3,"CMA-020":1.3,"BMD-001":1.15,"MEX-001":1.15,"PRD-002":1.05,"RSK-003":1.05}',
    "pharma_biotech":       '{"OPS-006":1.5,"FIN-001":1.5,"RSK-016":1.3,"BPL-003":1.3,"BMD-001":1.15,"SAL-002":1.15,"PRD-004":1.05,"TM-002":1.05}',
    "proptech":             '{"FIN-001":1.5,"SAL-002":1.5,"RSK-003":1.3,"OPS-006":1.3,"BMD-001":1.15,"GTM-003":1.15,"CMA-002":1.05,"OPS-001":1.05}',
    "retail":               '{"BMD-001":1.5,"FIN-001":1.5,"RSK-003":1.3,"GTM-007":1.3,"OPS-001":1.15,"OPS-005":1.15,"CMA-002":1.05,"PRD-004":1.05}',
    "sports_fitness":       '{"SAL-005":1.5,"BMD-001":1.5,"GTM-007":1.3,"RSK-003":1.3,"OPS-001":1.15,"SAL-003":1.15,"CMA-020":1.05,"MEX-001":1.05}',
    "telecom":              '{"SAL-005":1.5,"RSK-003":1.5,"OPS-006":1.3,"BMD-001":1.3,"FIN-001":1.15,"OPS-005":1.15,"SAL-003":1.05,"CMA-002":1.05}',
    "textiles":             '{"RSK-003":1.5,"FIN-001":1.5,"BMD-001":1.3,"PRD-004":1.3,"OPS-001":1.15,"OPS-003":1.15,"GTM-003":1.05,"TM-004":1.05}',
    "trade_import_export":  '{"RSK-002":1.5,"BMD-001":1.5,"FIN-001":1.3,"OPS-006":1.3,"RSK-003":1.15,"RSK-016":1.15,"SAL-003":1.05,"OPS-001":1.05}',
    "transport_delivery":   '{"BMD-001":1.5,"OPS-001":1.5,"SCL-039":1.3,"RSK-003":1.3,"TM-004":1.15,"OPS-005":1.15,"SAL-003":1.05,"OPS-006":1.05}',
    "travel_hospitality":   '{"FIN-001":1.5,"SCL-039":1.5,"BMD-001":1.3,"GTM-007":1.3,"PRD-004":1.15,"CMA-002":1.15,"OPS-001":1.05,"MEX-001":1.05}',
}


def _scalar(conn, sql, **params):
    return conn.execute(sa.text(sql), params).scalar()


def inspect_state(conn) -> dict:
    """What is true right now. Read-only, so the dry run is genuinely dry."""
    has_mapping = _scalar(conn, "SELECT to_regclass('public.question_industry_mapping')")
    return {
        "has_mapping_table": has_mapping is not None,
        "has_facts_table": _scalar(
            conn, "SELECT to_regclass('public.session_context_facts')") is not None,
        "mapping_rows": _scalar(conn, "SELECT count(*) FROM question_industry_mapping")
                        if has_mapping else 0,
        "industry_questions": _scalar(
            conn,
            "SELECT count(*) FROM questions WHERE industry_relevance IS NOT NULL "
            "AND industry_relevance <> '[\"all\"]'::jsonb"),
        "industries": _scalar(conn, "SELECT count(*) FROM industries"),
        "weighted": _scalar(
            conn,
            "SELECT count(*) FROM industries WHERE top_pain_point_weights <> '{}'::jsonb"),
    }


def verify(conn) -> list[str]:
    """Problems with the end state, empty when everything is right.

    Asserted rather than trusted: a mapping row whose industry_code resolves to
    nothing, or a weight naming a problem that does not exist, are both SILENT
    failures -- the feature would simply never fire for that industry, with no
    error anywhere.
    """
    problems: list[str] = []

    rows = _scalar(conn, "SELECT count(*) FROM question_industry_mapping")
    if rows != EXPECTED_MAPPING_ROWS:
        problems.append(f"mapping rows {rows}, expected {EXPECTED_MAPPING_ROWS}")

    inds = _scalar(conn, "SELECT count(DISTINCT industry_code) FROM question_industry_mapping")
    if inds != EXPECTED_INDUSTRIES:
        problems.append(f"industries mapped {inds}, expected {EXPECTED_INDUSTRIES}")

    lo = _scalar(conn, "SELECT min(c) FROM (SELECT count(*) c FROM "
                       "question_industry_mapping GROUP BY industry_code) s")
    hi = _scalar(conn, "SELECT max(c) FROM (SELECT count(*) c FROM "
                       "question_industry_mapping GROUP BY industry_code) s")
    if (lo, hi) != (EXPECTED_PER_INDUSTRY, EXPECTED_PER_INDUSTRY):
        problems.append(f"questions per industry {lo}-{hi}, expected "
                        f"{EXPECTED_PER_INDUSTRY} exactly")

    orphans = _scalar(conn,
                      "SELECT count(*) FROM question_industry_mapping m WHERE NOT EXISTS "
                      "(SELECT 1 FROM industries i WHERE i.industry_code = m.industry_code)")
    if orphans:
        problems.append(f"{orphans} mapping rows name an industry that does not exist")

    weighted = _scalar(conn, "SELECT count(*) FROM industries "
                             "WHERE top_pain_point_weights <> '{}'::jsonb")
    if weighted != EXPECTED_INDUSTRIES:
        problems.append(f"industries with weights {weighted}, expected {EXPECTED_INDUSTRIES}")

    entries = _scalar(conn, "SELECT count(*) FROM industries i, "
                            "jsonb_each(i.top_pain_point_weights) k")
    if entries != EXPECTED_WEIGHT_ENTRIES:
        problems.append(f"weight entries {entries}, expected {EXPECTED_WEIGHT_ENTRIES}")

    bad_codes = _scalar(conn,
                        "SELECT count(*) FROM industries i, jsonb_each(i.top_pain_point_weights) k "
                        "WHERE NOT EXISTS (SELECT 1 FROM problems p WHERE p.problem_code = k.key)")
    if bad_codes:
        problems.append(f"{bad_codes} weights name a problem_code that does not exist")

    return problems


def run(args) -> int:
    url = args.database_url or os.environ.get("DATABASE_URL")
    if not url:
        print("No --database-url and no DATABASE_URL in the environment.")
        return 2

    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    with engine.connect() as conn:
        before = inspect_state(conn)

    print("=" * 68)
    print("BEFORE")
    print("=" * 68)
    for k, v in before.items():
        print(f"  {k:24} {v}")

    if before["industry_questions"] == 0:
        print("\n  STOP: this database has no industry-tagged questions, so the")
        print("  industry seed migrations have never run here. This script")
        print("  cannot invent them -- fix that first.")
        return 2

    if not args.confirm_writes:
        print("\n  Dry run. Nothing was written.")
        print("  Re-run with --confirm-writes to apply.")
        return 0

    with engine.begin() as conn:
        for statement in filter(None, (s.strip() for s in _DDL.split(";"))):
            conn.execute(sa.text(statement))

        inserted = conn.execute(sa.text(_FILL_MAPPING)).rowcount

        updated = 0
        for code, weights in _WEIGHTS.items():
            updated += conn.execute(
                sa.text(
                    "UPDATE industries SET top_pain_point_weights = CAST(:w AS jsonb), "
                    "updated_at = now() WHERE industry_code = :c "
                    "AND (top_pain_point_weights = '{}'::jsonb "
                    "     OR top_pain_point_weights IS NULL)"
                ),
                {"w": weights, "c": code},
            ).rowcount

        # Decided from the database, never assumed. See _CAN_SAFELY_ENABLE_RLS.
        rls_safe = bool(conn.execute(sa.text(_CAN_SAFELY_ENABLE_RLS)).scalar())
        if rls_safe:
            for statement in _ENABLE_RLS:
                conn.execute(sa.text(statement))

    print(f"\n  mapping rows inserted : {inserted}")
    print(f"  industries weighted   : {updated}")
    if rls_safe:
        print("  row-level security    : enabled (this role owns the tables "
              "or bypasses RLS)")
    else:
        print("  row-level security    : LEFT OFF -- this role neither owns the")
        print("                          tables nor bypasses RLS, so enabling it")
        print("                          would make the backend read zero rows.")
        print("                          Correct for RDS. See the note in")
        print("                          data/rds/001_industry_selection_tables.sql")
        print("                          for how to add it properly later.")

    with engine.connect() as conn:
        problems = verify(conn)
        after = inspect_state(conn)

    print("\n" + "=" * 68)
    print("AFTER")
    print("=" * 68)
    for k, v in after.items():
        print(f"  {k:24} {v}")

    if problems:
        print("\n  VERIFICATION FAILED:")
        for p in problems:
            print(f"    - {p}")
        return 1

    print("\n  VERIFIED. The industry feature is live on this database.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", default=None,
                   help="defaults to $DATABASE_URL, which ECS already sets")
    p.add_argument("--confirm-writes", action="store_true",
                   help="without this nothing is written")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
