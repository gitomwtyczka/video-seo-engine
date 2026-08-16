"""add short_candidate_sets table

Revision ID: 20260816_add_short_candidate_sets
Down revision: 20260816_short_jobs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table(
        'short_candidate_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('youtube_id', sa.String(20), nullable=False),
        sa.Column('youtube_url', sa.String(500), nullable=True),
        sa.Column('portal_id', sa.String(100), nullable=True),
        sa.Column('custom_query', sa.Text, nullable=True),
        sa.Column('candidates', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('version', sa.Integer, default=1, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_short_candidate_sets_youtube_id', 'short_candidate_sets', ['youtube_id'])

def downgrade():
    op.drop_table('short_candidate_sets')
