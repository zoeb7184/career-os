"""
Initial migration — creates all tables.
Generated: Phase 1
Run: alembic upgrade head
"""
import sqlalchemy as sa
from alembic import op

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table('users',
        sa.Column('id',            sa.String(36),  primary_key=True),
        sa.Column('email',         sa.String(320), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('provider',      sa.String(20),  server_default='email'),
        sa.Column('provider_id',   sa.String(255)),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('preferences',   sa.JSON, server_default='{}'),
    )

    # skills taxonomy
    op.create_table('skills',
        sa.Column('id',             sa.String(36),  primary_key=True),
        sa.Column('canonical_name', sa.String(200), unique=True, nullable=False),
        sa.Column('category',       sa.String(50)),
        sa.Column('aliases',        sa.ARRAY(sa.Text)),
    )

    # jobs
    op.create_table('jobs',
        sa.Column('id',               sa.String(36),  primary_key=True),
        sa.Column('source',           sa.String(50),  nullable=False),
        sa.Column('external_id',      sa.String(255), nullable=False),
        sa.Column('title',            sa.String(500), nullable=False),
        sa.Column('company',          sa.String(500)),
        sa.Column('location',         sa.String(500)),
        sa.Column('country',          sa.String(10)),
        sa.Column('remote_type',      sa.String(20)),
        sa.Column('salary_min',       sa.Numeric(12, 2)),
        sa.Column('salary_max',       sa.Numeric(12, 2)),
        sa.Column('description',      sa.Text),
        sa.Column('description_hash', sa.String(64)),
        sa.Column('posted_at',        sa.DateTime(timezone=True)),
        sa.Column('expires_at',       sa.DateTime(timezone=True)),
        sa.Column('is_active',        sa.Boolean, server_default='true'),
        sa.Column('ingested_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('embedding_id',     sa.String(100)),
        sa.UniqueConstraint('source', 'external_id', name='uq_jobs_source_external'),
    )
    op.create_index('ix_jobs_is_active',  'jobs', ['is_active'])
    op.create_index('ix_jobs_country',    'jobs', ['country'])
    op.create_index('ix_jobs_source',     'jobs', ['source'])
    op.create_index('ix_jobs_posted_at',  'jobs', ['posted_at'])
    op.create_index('ix_jobs_desc_hash',  'jobs', ['description_hash'])

    # job_skills
    op.create_table('job_skills',
        sa.Column('job_id',     sa.String(36), sa.ForeignKey('jobs.id',   ondelete='CASCADE'), nullable=False),
        sa.Column('skill_id',   sa.String(36), sa.ForeignKey('skills.id'), nullable=False),
        sa.Column('skill_type', sa.String(20)),
        sa.Column('importance', sa.Float, server_default='1.0'),
        sa.PrimaryKeyConstraint('job_id', 'skill_id'),
    )

    # resumes
    op.create_table('resumes',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('user_id',          sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('filename',         sa.String(500)),
        sa.Column('raw_text',         sa.Text),
        sa.Column('parsed_sections',  sa.JSON),
        sa.Column('embedding_id',     sa.String(100)),
        sa.Column('uploaded_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # applications
    op.create_table('applications',
        sa.Column('id',         sa.String(36), primary_key=True),
        sa.Column('user_id',    sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('job_id',     sa.String(36), sa.ForeignKey('jobs.id')),
        sa.Column('status',     sa.String(30), server_default='saved'),
        sa.Column('ats_score',  sa.Float),
        sa.Column('notes',      sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # market_snapshots (for forecasting)
    op.create_table('market_snapshots',
        sa.Column('id',            sa.String(36), primary_key=True),
        sa.Column('snapshot_date', sa.Date, nullable=False),
        sa.Column('skill_id',      sa.String(36), sa.ForeignKey('skills.id')),
        sa.Column('country',       sa.String(10)),
        sa.Column('demand',        sa.Integer),
        sa.Column('avg_salary',    sa.Numeric(12, 2)),
        sa.UniqueConstraint('snapshot_date', 'skill_id', 'country', name='uq_snapshot'),
    )


def downgrade() -> None:
    op.drop_table('market_snapshots')
    op.drop_table('applications')
    op.drop_table('resumes')
    op.drop_table('job_skills')
    op.drop_table('jobs')
    op.drop_table('skills')
    op.drop_table('users')
