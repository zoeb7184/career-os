"""
Smart Import — adds the `imports` table (one row per uploaded file) and the
applications columns it populates (applied_at, platform, import_id).
"""
import sqlalchemy as sa
from alembic import op

revision = '0003_smart_import'
down_revision = '0002_url_and_resume_skills'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('imports',
        sa.Column('id',              sa.String(36),  primary_key=True),
        sa.Column('user_id',         sa.String(36),  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename',        sa.String(500)),
        sa.Column('file_type',       sa.String(10)),
        sa.Column('total_rows',      sa.Integer,     server_default='0'),
        sa.Column('imported_rows',   sa.Integer,     server_default='0'),
        sa.Column('skipped_rows',    sa.Integer,     server_default='0'),
        sa.Column('duplicate_count', sa.Integer,     server_default='0'),
        sa.Column('status_counts',   sa.JSON,        server_default='{}'),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_imports_user_id', 'imports', ['user_id'])

    op.add_column('applications', sa.Column('applied_at', sa.Date))
    op.add_column('applications', sa.Column('platform', sa.String(100)))
    op.add_column('applications', sa.Column(
        'import_id', sa.String(36), sa.ForeignKey('imports.id', ondelete='SET NULL')
    ))
    op.create_index('ix_applications_import_id', 'applications', ['import_id'])


def downgrade() -> None:
    op.drop_index('ix_applications_import_id', table_name='applications')
    op.drop_column('applications', 'import_id')
    op.drop_column('applications', 'platform')
    op.drop_column('applications', 'applied_at')
    op.drop_index('ix_imports_user_id', table_name='imports')
    op.drop_table('imports')
