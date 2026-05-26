"""user bot settings

Revision ID: 0004_user_bot_settings
Revises: 0003_users_and_exchange_accounts
Create Date: 2026-05-26 14:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '0004_user_bot_settings'
down_revision = '0003_users_and_exchange_accounts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'user_bot_settings' not in set(inspector.get_table_names()):
        op.create_table(
            'user_bot_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('mode', sa.String(length=32), nullable=False, server_default='DRY_RUN'),
            sa.Column('selected_exchange', sa.String(length=32), nullable=False, server_default='kraken'),
            sa.Column('symbols', sa.String(length=120), nullable=False, server_default='BTC,ETH'),
            sa.Column('paper_balance', sa.Float(), nullable=False, server_default='5000'),
            sa.Column('max_open_positions', sa.Integer(), nullable=False, server_default='2'),
            sa.Column('risk_profile', sa.String(length=64), nullable=False, server_default='balanced'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
    indexes = {index['name'] for index in sa.inspect(bind).get_indexes('user_bot_settings')}
    if 'ix_user_bot_settings_user_id' not in indexes:
        op.create_index('ix_user_bot_settings_user_id', 'user_bot_settings', ['user_id'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if 'user_bot_settings' in set(sa.inspect(bind).get_table_names()):
        indexes = {index['name'] for index in sa.inspect(bind).get_indexes('user_bot_settings')}
        if 'ix_user_bot_settings_user_id' in indexes:
            op.drop_index('ix_user_bot_settings_user_id', table_name='user_bot_settings')
        op.drop_table('user_bot_settings')
