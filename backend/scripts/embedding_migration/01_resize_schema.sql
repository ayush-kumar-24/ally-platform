-- ===========================================================================
-- Embedding migration 01/03 -- SCHEMA: resize vector columns 384 -> 1536
-- ===========================================================================
-- DESTRUCTIVE. This DROPS every existing gte-small (384-d) vector. You cannot
-- resize a pgvector column that still holds 384-d data, so each embedding is set
-- to NULL first, the column is widened to vector(1536), and the HNSW index is
-- rebuilt. Regenerate the vectors with 02_regenerate_embeddings.py immediately
-- after, then confirm with 03_verify_embeddings.py.
--
-- Take a database backup before running. Retrieval returns nothing between this
-- step and the completion of 02 (all embeddings are NULL in that window).
--
-- Runs in one transaction. Review, then execute against the target database.
-- ===========================================================================

BEGIN;

-- --- root_causes ---
DROP INDEX IF EXISTS idx_root_causes_embedding;
UPDATE root_causes SET embedding = NULL;
ALTER TABLE root_causes ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS embedding_model varchar;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS embedding_version varchar;
CREATE INDEX idx_root_causes_embedding ON root_causes
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- --- problems ---
DROP INDEX IF EXISTS idx_problems_embedding;
UPDATE problems SET embedding = NULL;
ALTER TABLE problems ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE problems ADD COLUMN IF NOT EXISTS embedding_model varchar;
ALTER TABLE problems ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE problems ADD COLUMN IF NOT EXISTS embedding_version varchar;
CREATE INDEX idx_problems_embedding ON problems
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- --- questions ---
DROP INDEX IF EXISTS idx_questions_embedding;
UPDATE questions SET embedding = NULL;
ALTER TABLE questions ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS embedding_model varchar;
ALTER TABLE questions ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE questions ADD COLUMN IF NOT EXISTS embedding_version varchar;
CREATE INDEX idx_questions_embedding ON questions
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- --- agent_interpretations ---
DROP INDEX IF EXISTS idx_agent_interpretations_embedding;
UPDATE agent_interpretations SET embedding = NULL;
ALTER TABLE agent_interpretations ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE agent_interpretations ADD COLUMN IF NOT EXISTS embedding_model varchar;
ALTER TABLE agent_interpretations ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE agent_interpretations ADD COLUMN IF NOT EXISTS embedding_version varchar;
CREATE INDEX idx_agent_interpretations_embedding ON agent_interpretations
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- --- behaviour_patterns ---
DROP INDEX IF EXISTS idx_behaviour_patterns_embedding;
UPDATE behaviour_patterns SET embedding = NULL;
ALTER TABLE behaviour_patterns ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE behaviour_patterns ADD COLUMN IF NOT EXISTS embedding_model varchar;
ALTER TABLE behaviour_patterns ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE behaviour_patterns ADD COLUMN IF NOT EXISTS embedding_version varchar;
CREATE INDEX idx_behaviour_patterns_embedding ON behaviour_patterns
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- --- archetypes ---
DROP INDEX IF EXISTS idx_archetypes_embedding;
UPDATE archetypes SET embedding = NULL;
ALTER TABLE archetypes ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE archetypes ADD COLUMN IF NOT EXISTS embedding_model varchar;
ALTER TABLE archetypes ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE archetypes ADD COLUMN IF NOT EXISTS embedding_version varchar;
CREATE INDEX idx_archetypes_embedding ON archetypes
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- --- rag_chunks (embedding is NOT NULL -> relax it so we can clear + resize) ---
DROP INDEX IF EXISTS idx_rag_chunks_embedding;
ALTER TABLE rag_chunks ALTER COLUMN embedding DROP NOT NULL;
UPDATE rag_chunks SET embedding = NULL;
ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(1536);
ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding_dimension integer;
CREATE INDEX idx_rag_chunks_embedding ON rag_chunks
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
-- Re-add NOT NULL after 02 has repopulated, if you want to enforce it:
--   ALTER TABLE rag_chunks ALTER COLUMN embedding SET NOT NULL;

COMMIT;
