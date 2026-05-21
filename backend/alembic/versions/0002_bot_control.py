"""bot control state

Revision ID: 0002_bot_control
Revises: 0001_initial_schema
Create Date: 2026-05-20 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = '0002_bot_control'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bot_control',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('mode', sa.String(length=32), nullable=False, server_default='DRY_RUN'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.String(length=64), nullable=False, server_default='system'),
        sa.Column('note', sa.Text(), nullable=True),
    )
    op.bulk_insert(
        sa.table(
            'bot_control',
            sa.column('id', sa.Integer()),
            sa.column('active', sa.Boolean()),
            sa.column('mode', sa.String(length=32)),
            sa.column('updated_at', sa.DateTime()),
            sa.column('updated_by', sa.String(length=64)),
            sa.column('note', sa.Text()),
        ),
        [{
            'id': 1,
            'active': True,
            'mode': 'DRY_RUN',
            'updated_at': datetime.utcnow(),
            'updated_by': 'migration',
            'note': 'Default bot control initialized in DRY_RUN mode.',
        }],
    )


def downgrade() -> None:
    op.drop_table('bot_control')
