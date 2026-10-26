"""Initial schema with vector extension and HNSW index

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-09 04:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from backend.config import settings

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create articles table
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('topic', sa.String(length=50), nullable=False, server_default='general'),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_articles_source', 'articles', ['source'], unique=False)
    op.create_index('ix_articles_url', 'articles', ['url'], unique=True)
    op.create_index('ix_articles_published_at', 'articles', ['published_at'], unique=False)
    op.create_index('ix_articles_topic', 'articles', ['topic'], unique=False)
    op.create_index('ix_articles_language', 'articles', ['language'], unique=False)
    op.create_index('ix_articles_content_hash', 'articles', ['content_hash'], unique=True)

    # 3. Create chunks table
    op.create_table(
        'chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(settings.EMBEDDING_DIM), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('doc_type', sa.String(length=20), nullable=False, server_default='news'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chunks_article_id', 'chunks', ['article_id'], unique=False)
    op.create_index('ix_chunks_source', 'chunks', ['source'], unique=False)
    op.create_index('ix_chunks_published_at', 'chunks', ['published_at'], unique=False)
    op.create_index('ix_chunks_doc_type', 'chunks', ['doc_type'], unique=False)

    # 4. Create HNSW index on chunk embeddings
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )

    # 5. Create fact_checks table
    op.create_table(
        'fact_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('claim', sa.Text(), nullable=False),
        sa.Column('claimant', sa.String(length=255), nullable=True),
        sa.Column('rating', sa.String(length=100), nullable=False),
        sa.Column('review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('publisher', sa.String(length=100), nullable=False),
        sa.Column('review_url', sa.String(length=1000), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_fact_checks_publisher', 'fact_checks', ['publisher'], unique=False)
    op.create_index('ix_fact_checks_review_date', 'fact_checks', ['review_date'], unique=False)
    op.create_index('ix_fact_checks_content_hash', 'fact_checks', ['content_hash'], unique=True)

    # 6. Create chat_logs table (No personal data: no IP, no names)
    op.create_table(
        'chat_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('user_query', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=50), nullable=False),
        sa.Column('detected_language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('verdict', sa.String(length=50), nullable=True),
        sa.Column('confidence', sa.String(length=20), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('sources_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_logs_session_id', 'chat_logs', ['session_id'], unique=False)
    op.create_index('ix_chat_logs_intent', 'chat_logs', ['intent'], unique=False)
    op.create_index('ix_chat_logs_verdict', 'chat_logs', ['verdict'], unique=False)
    op.create_index('ix_chat_logs_created_at', 'chat_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('chat_logs')
    op.drop_table('fact_checks')
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;")
    op.drop_table('chunks')
    op.drop_table('articles')
    # Dropping the extension is optional or commented to prevent breaking other DB users
    # op.execute("DROP EXTENSION IF EXISTS vector;")
