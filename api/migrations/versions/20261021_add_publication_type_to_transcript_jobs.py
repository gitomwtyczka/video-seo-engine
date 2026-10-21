"""add publication_type to transcript_jobs

Revision ID: 20261021_add_publication_type
Revises: 20260816_add_short_candidate_sets
Create Date: 2026-10-21 11:00:00
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("ALTER TABLE transcript_jobs ADD COLUMN IF NOT EXISTS publication_type VARCHAR(50);")
    op.execute("UPDATE transcript_jobs SET publication_type = COALESCE(schema_data->>'publication_type', 'full_analysis') WHERE publication_type IS NULL;")


def downgrade():
    op.drop_column('transcript_jobs', 'publication_type')
