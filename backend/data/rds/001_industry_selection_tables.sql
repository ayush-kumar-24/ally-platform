-- ===========================================================================
-- Industry-adaptive question selection: the tables the feature reads.
--
-- FOR THE AWS TEAM. Run this against the production RDS instance. It is plain
-- PostgreSQL, additive only, and idempotent -- safe to run twice.
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f 001_industry_selection_tables.sql
--
-- RDS is not reachable from outside the VPC, so run it the way DEPLOY.md runs
-- every other one-off: `aws ecs run-task` against ally-backend-cluster, reusing
-- the service image and secrets, and read the result from CloudWatch.
--
-- ---------------------------------------------------------------------------
-- WHY THIS FILE EXISTS INSTEAD OF `alembic upgrade head`
--
-- Two independent reasons, both pre-existing and neither introduced here:
--
--   The SUPABASE test instance carries an ORPHANED STAMP in alembic_version --
--   `f8a3c26e4b91`, a revision that exists in no file in this repository -- so
--   alembic refuses to start from it THERE. It is also genuinely behind: the
--   head migration's effect (RLS on five tables) is absent. Already documented
--   in scripts/_apply_dimension_code_column.py, which hit the same wall.
--
--   PRODUCTION IS NOT AFFECTED. RDS has a valid stamp and migrates normally --
--   backend-deploy.yml runs `alembic upgrade head` on every deploy and
--   hard-fails on a non-zero exit, and it has been succeeding.
--
--   An earlier version of this comment also claimed "the migration graph has
--   TEN HEADS". THAT WAS WRONG. It came from a hand-rolled parser that missed
--   merge revisions and saw only 91 of the real 130. Alembic itself reports
--   exactly ONE head, c9f41b8e3a07. The claim is corrected here rather than
--   deleted, because it was handed to the AWS team in this file.
--
--   So this file applies the exact DDL from
--     alembic/versions/2026_09_18_1758-62ebd946ebc0_industry_stage_structure.py
--   directly, and DOES NOT TOUCH alembic_version. On RDS these statements are
--   the no-op `alembic upgrade head` would have made anyway, which is why they
--   are written idempotently. Reconciling Supabase's stamp needs an audit of
--   which migrations actually ran there -- not a blind `alembic stamp head`,
--   which would skip real work -- and that is separate from a schema fix.
--
-- ---------------------------------------------------------------------------
-- WHAT BREAKS WITHOUT IT
--
-- The selection code fails OPEN by design: a missing table disables the
-- industry feature silently. No error, no startup warning, no wrong answer --
-- it simply behaves as it did before the feature was written. Which means the
-- 1,800 industry-specific questions stay eligible for EVERY founder.
--
-- Measured on the database this was first applied to, at Stage 1->10+:
--
--     universal questions (everyone)      1,478
--     the founder's own industry             25
--     OTHER INDUSTRIES' questions           725   <- wrongly eligible
--
-- 725 questions per founder, per stage. A logistics founder was a valid
-- candidate for "Do you have any security certification buyers recognise?"
-- and a SaaS founder for "Out of 100 deliveries, how many arrive damaged?".
-- ===========================================================================

\set ON_ERROR_STOP on

BEGIN;

-- --------------------------------------------------------------------------
-- 1. question_industry_mapping -- the link the whole feature reads.
--
-- A question with NO row here is universal and reaches everyone. That is the
-- rule, and it is why this table can never shrink the general bank.
-- --------------------------------------------------------------------------
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

-- --------------------------------------------------------------------------
-- 2. session_context_facts -- session-scoped "this does not apply to me".
--
-- Created by the same migration and read by nothing yet. Included so the two
-- databases match and the N/A work does not need a second RDS change.
-- --------------------------------------------------------------------------
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

-- --------------------------------------------------------------------------
-- 3. question_tags.precondition_token -- same migration, same reason.
-- --------------------------------------------------------------------------
ALTER TABLE question_tags
    ADD COLUMN IF NOT EXISTS precondition_token VARCHAR DEFAULT NULL;

COMMENT ON COLUMN question_tags.precondition_token IS
'Nullable. If set (e.g. has_team, fundraising_intent), a question with this tag should only be shown when that condition is known to be true. NULL means no precondition -- do not set this on every tag automatically, only where genuinely required.';

-- --------------------------------------------------------------------------
-- 4. Fill the mapping FROM THE DATABASE'S OWN DATA.
--
-- Deliberately derived from questions.industry_relevance rather than from a
-- hard-coded list of 1,800 ids. Two reasons: the ids are surrogate keys that
-- differ between instances, so a literal list would be wrong on any database
-- but the one it was generated from; and the seed migrations already wrote
-- industry_relevance on every industry question, so it is the authoritative
-- statement of which question belongs to which industry.
--
-- '["all"]' is the default for every generic question and is excluded here --
-- those are the universal ones that must keep reaching everyone.
--
-- 'primary' for all of them, matching what the seed migrations inserted. The
-- 'supporting' grade exists in the CHECK constraint for content that is graded
-- later; nothing produces it yet.
--
-- ON CONFLICT DO NOTHING makes a re-run a no-op.
-- --------------------------------------------------------------------------
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
ON CONFLICT (question_id, industry_code, stage_group) DO NOTHING;

-- --------------------------------------------------------------------------
-- 5. Row-level security -- DELIBERATELY NOT ENABLED HERE.
--
-- An earlier draft of this file ran
--     ALTER TABLE question_industry_mapping ENABLE ROW LEVEL SECURITY;
-- and justified it as "a no-op on RDS, there is no PostgREST in front of it".
-- That reasoning was WRONG and the statement would have broken production.
--
-- What makes RLS harmless is the CONNECTING ROLE, not the API in front of the
-- database. Measured on both instances:
--
--     Supabase   tables owned by postgres; the app connects as postgres,
--                which has rolbypassrls = true  -> RLS never applies
--     RDS        the app connects as ally_app, which does NOT own these
--                tables, does NOT have BYPASSRLS, and there are no policies
--                -> RLS ON means ally_app reads ZERO rows
--
-- Zero rows is the exact silent failure this feature is built to avoid. The
-- selection code fails open, so it would not error -- it would quietly stop
-- gating industries again, indistinguishable from the table being missing.
--
-- So RLS stays OFF on RDS, where the table is reachable only from inside the
-- VPC by an application role. The Supabase instance keeps it ON because it
-- sits behind PostgREST on the public internet, and every other reference
-- table there does the same.
--
-- TO ENABLE IT ON RDS LATER, the policy must exist FIRST and must name the
-- role that actually connects:
--
--     CREATE POLICY qim_read ON question_industry_mapping
--         FOR SELECT TO ally_app USING (true);
--     ALTER TABLE question_industry_mapping ENABLE ROW LEVEL SECURITY;
--
-- Check the role before trusting any of this:
--
--     SELECT current_user,
--            (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user),
--            pg_get_userbyid(relowner)
--       FROM pg_class WHERE relname = 'question_industry_mapping';
-- --------------------------------------------------------------------------

COMMIT;

-- ===========================================================================
-- VERIFICATION -- run this after, and read it before updating the service.
--
-- Expected on a correctly seeded database:
--   mapping_rows      1800
--   industries_mapped   30
--   min/max_per_ind   60 / 60
--   stage_groups         3     (15 Stage 0, 20 Stage 0->1, 25 Stage 1->10+)
--   orphan_industries    0     (every code resolves to an industries row)
--
-- A mapping_rows of 0 means the industry seed migrations have not run on this
-- database. Fix that first -- this file cannot invent the questions.
-- ===========================================================================
SELECT
    (SELECT count(*) FROM question_industry_mapping)                    AS mapping_rows,
    (SELECT count(DISTINCT industry_code) FROM question_industry_mapping) AS industries_mapped,
    (SELECT min(c) FROM (SELECT count(*) c FROM question_industry_mapping
                         GROUP BY industry_code) s)                     AS min_per_industry,
    (SELECT max(c) FROM (SELECT count(*) c FROM question_industry_mapping
                         GROUP BY industry_code) s)                     AS max_per_industry,
    (SELECT count(DISTINCT stage_group) FROM question_industry_mapping) AS stage_groups,
    (SELECT count(*) FROM question_industry_mapping m
      WHERE NOT EXISTS (SELECT 1 FROM industries i
                        WHERE i.industry_code = m.industry_code))       AS orphan_industries;

-- What this actually buys, per stage band: how many of ANOTHER industry's
-- questions a founder is now shielded from. Expected 435 / 580 / 725.
--
-- Matched on industry_code rather than on the stage_group text, because that
-- column holds a Unicode arrow ("Stage 0->1" is really "Stage 0→1") and a
-- literal would depend on the client encoding. Grouping avoids typing it.
SELECT m.stage_group,
       count(*)                                                AS industry_owned,
       count(*) FILTER (WHERE m.industry_code <> 'saas')        AS blocked_for_saas_founder
FROM question_industry_mapping m
GROUP BY m.stage_group
ORDER BY m.stage_group;
