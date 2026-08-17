"""align vector dimensions to openai embeddings

Revision ID: e29b1b0a58f6
Revises: d91c6e4b72aa
Create Date: 2026-08-15 11:06
"""

from alembic import op


revision = "e29b1b0a58f6"
down_revision = "d91c6e4b72aa"
branch_labels = None
depends_on = None


VECTOR_INDEXES = [
    (
        "idx_agent_interpretations_embedding",
        "agent_interpretations",
        "CREATE INDEX idx_agent_interpretations_embedding "
        "ON public.agent_interpretations USING hnsw "
        "(embedding vector_cosine_ops) WHERE (embedding IS NOT NULL)",
    ),
    (
        "idx_archetypes_embedding",
        "archetypes",
        "CREATE INDEX idx_archetypes_embedding "
        "ON public.archetypes USING hnsw "
        "(embedding vector_cosine_ops)",
    ),
    (
        "idx_behaviour_patterns_embedding",
        "behaviour_patterns",
        "CREATE INDEX idx_behaviour_patterns_embedding "
        "ON public.behaviour_patterns USING hnsw "
        "(embedding vector_cosine_ops) WHERE (embedding IS NOT NULL)",
    ),
    (
        "idx_problems_embedding",
        "problems",
        "CREATE INDEX idx_problems_embedding "
        "ON public.problems USING hnsw "
        "(embedding vector_cosine_ops) WHERE (embedding IS NOT NULL)",
    ),
    (
        "idx_questions_embedding",
        "questions",
        "CREATE INDEX idx_questions_embedding "
        "ON public.questions USING hnsw "
        "(embedding vector_cosine_ops) WHERE (embedding IS NOT NULL)",
    ),
    (
        "idx_rag_chunks_embedding",
        "rag_chunks",
        "CREATE INDEX idx_rag_chunks_embedding "
        "ON public.rag_chunks USING hnsw "
        "(embedding vector_cosine_ops)",
    ),
    (
        "idx_root_causes_embedding",
        "root_causes",
        "CREATE INDEX idx_root_causes_embedding "
        "ON public.root_causes USING hnsw "
        "(embedding vector_cosine_ops) WHERE (embedding IS NOT NULL)",
    ),
]

VECTOR_TABLES = [
    "agent_interpretations",
    "archetypes",
    "behaviour_patterns",
    "problems",
    "questions",
    "rag_chunks",
    "root_causes",
]


def _drop_vector_indexes() -> None:
    for index_name, _, _ in VECTOR_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS public.{index_name}")


def _create_vector_indexes() -> None:
    for _, _, create_sql in VECTOR_INDEXES:
        op.execute(create_sql)


def upgrade() -> None:
    _drop_vector_indexes()

    for table in VECTOR_TABLES:
        op.execute(
            f"""
            ALTER TABLE public.{table}
            ALTER COLUMN embedding
            TYPE vector(1536)
            USING embedding::vector(1536)
            """
        )

    op.execute(
        """
        ALTER TABLE public.rag_chunks
        ALTER COLUMN embedding_model
        SET DEFAULT 'text-embedding-3-small'
        """
    )

    _create_vector_indexes()


def downgrade() -> None:
    _drop_vector_indexes()

    op.execute(
        """
        ALTER TABLE public.rag_chunks
        ALTER COLUMN embedding_model
        SET DEFAULT 'gte-small'
        """
    )

    for table in VECTOR_TABLES:
        op.execute(
            f"""
            ALTER TABLE public.{table}
            ALTER COLUMN embedding
            TYPE vector(384)
            USING embedding::vector(384)
            """
        )

    _create_vector_indexes()
