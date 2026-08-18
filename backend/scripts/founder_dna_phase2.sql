-- Founder DNA phase-2 tables (migration f4a2c8e91b36, applied manually).
--
-- Run this in the Supabase SQL editor, or:
--   psql "<DATABASE_URL>" -f scripts/founder_dna_phase2.sql
--
-- Idempotent (IF NOT EXISTS throughout) -- safe to re-run.
--
-- NOTE: this applies the DDL only. It does NOT stamp alembic_version,
-- because the migration chain is still blocked upstream at f2f3d7d7ce11
-- (the missing `ally_app` role). Once that is resolved, run
-- `alembic stamp f4a2c8e91b36` so Alembic's history matches reality --
-- otherwise a later `alembic upgrade head` will try to CREATE these tables
-- again (they'd no-op on IF NOT EXISTS, but the history would still be
-- wrong, which is exactly the drift problem this project already hit once).

CREATE TABLE IF NOT EXISTS founder_dna_questions (
    founder_dna_question_id SERIAL PRIMARY KEY,
    dimension_code VARCHAR(30) NOT NULL,
    stage_group VARCHAR(20) NOT NULL,
    format VARCHAR(20) DEFAULT 'narrative' NOT NULL,
    question_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT founder_dna_questions_dimension_code_check
        CHECK (dimension_code = ANY (ARRAY[
            'purpose_mission','core_values','mindset_excellence',
            'energy_patterns','decision_style','focus_attention'
        ]::text[])),
    CONSTRAINT founder_dna_questions_stage_group_check
        CHECK (stage_group = ANY (ARRAY['Stage 0','Stage 0→1','Stage 1→10+']::text[])),
    CONSTRAINT founder_dna_questions_format_check
        CHECK (format = ANY (ARRAY['narrative','scenario']::text[]))
);

CREATE INDEX IF NOT EXISTS idx_founder_dna_questions_dimension_stage
    ON founder_dna_questions (dimension_code, stage_group);

CREATE TABLE IF NOT EXISTS founder_dna_answers (
    founder_dna_answer_id SERIAL PRIMARY KEY,
    founder_id INTEGER NOT NULL
        REFERENCES founders (founder_id) ON DELETE CASCADE,
    founder_dna_question_id INTEGER NOT NULL
        REFERENCES founder_dna_questions (founder_dna_question_id),
    answer_text TEXT NOT NULL,
    answered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_founder_dna_answers_founder
    ON founder_dna_answers (founder_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_founder_dna_answers_founder_question
    ON founder_dna_answers (founder_id, founder_dna_question_id);

ALTER TABLE founders
    ADD COLUMN IF NOT EXISTS founder_dna_completed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE founders
    ADD COLUMN IF NOT EXISTS founder_dna_resolved_dimensions
    JSONB NOT NULL DEFAULT '[]'::jsonb;
