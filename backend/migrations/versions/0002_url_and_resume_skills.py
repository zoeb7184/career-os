"""
Adds jobs.url (referenced by GET /jobs/{id} but never created in 0001) and
the resume_skills table (referenced by GET /recommend/{user_id} but never
created in 0001).
"""
import sqlalchemy as sa
from alembic import op

revision = '0002_url_and_resume_skills'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('url', sa.String(1000)))

    op.create_table('resume_skills',
        sa.Column('resume_id',  sa.String(36), sa.ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('skill_id',   sa.String(36), sa.ForeignKey('skills.id'), nullable=False),
        sa.Column('importance', sa.Float, server_default='1.0'),
        sa.PrimaryKeyConstraint('resume_id', 'skill_id'),
    )


def downgrade() -> None:
    op.drop_table('resume_skills')
    op.drop_column('jobs', 'url')
