"""add external_insight document type and knowledge_domain

Revision ID: e7b3c9d21f4a
Revises: c3d1f0a2b7e4
Create Date: 2026-07-30 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7b3c9d21f4a'
down_revision: Union[str, Sequence[str], None] = 'c3d1f0a2b7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Allow podcast / external content as a document type
    op.drop_constraint('rag_documents_document_type_check', 'rag_documents', type_='check')
    op.create_check_constraint(
        'rag_documents_document_type_check',
        'rag_documents',
        "document_type IN ('client_report','case_study','consultant_note',"
        "'playbook','service_offering','external_insight')"
    )

    # 2. Knowledge domain -- required for the agentic router, and cheaper to add
    #    now than to backfill across a growing corpus later
    op.add_column('rag_documents', sa.Column('knowledge_domain', sa.Text(), nullable=True))
    op.create_check_constraint(
        'rag_documents_knowledge_domain_check',
        'rag_documents',
        "knowledge_domain IS NULL OR knowledge_domain IN "
        "('founder_knowledge','goxl_knowledge','business_resources','learning_content')"
    )

    # 3. Backfill the six existing documents
    op.execute("UPDATE rag_documents SET knowledge_domain = 'goxl_knowledge'")

    op.create_index('ix_rag_documents_knowledge_domain', 'rag_documents', ['knowledge_domain'])


def downgrade() -> None:
    op.drop_index('ix_rag_documents_knowledge_domain', table_name='rag_documents')
    op.drop_constraint('rag_documents_knowledge_domain_check', 'rag_documents', type_='check')
    op.drop_column('rag_documents', 'knowledge_domain')
    op.drop_constraint('rag_documents_document_type_check', 'rag_documents', type_='check')
    op.create_check_constraint(
        'rag_documents_document_type_check',
        'rag_documents',
        "document_type IN ('client_report','case_study','consultant_note',"
        "'playbook','service_offering')"
    )
