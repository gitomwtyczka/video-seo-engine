"""add short_jobs table

Revision ID: 20260816_short_jobs
Down revision: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table(
        'short_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('youtube_url', sa.String(500), nullable=True),
        sa.Column('local_path', sa.String(1000), nullable=True),
        sa.Column('youtube_id', sa.String(20), nullable=True),
        sa.Column('start_sec', sa.Float, nullable=False),
        sa.Column('end_sec', sa.Float, nullable=False),
        sa.Column('candidate_data', postgresql.JSONB, nullable=True),
        sa.Column('render_config', postgresql.JSONB, nullable=True),
        sa.Column('result_paths', postgresql.JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('portal_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_short_jobs_status', 'short_jobs', ['status'])

def downgrade():
    op.drop_table('short_jobs')
