"""users and exchange accounts

Revision ID: 0003_users_and_exchange_accounts
Revises: 0002_bot_control
Create Date: 2026-05-26 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '0003_users_and_exchange_accounts'
down_revision = '0002_bot_control'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('paper_trading', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )

    user_indexes = {index['name'] for index in inspector.get_indexes('users')}
    if 'ix_users_email' not in user_indexes:
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    tables = set(sa.inspect(bind).get_table_names())
    if 'user_exchange_accounts' not in tables:
        op.create_table(
            'user_exchange_accounts',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('exchange', sa.String(length=32), nullable=False),
            sa.Column('account_label', sa.String(length=80), nullable=False, server_default='main'),
            sa.Column('api_key_encrypted', sa.Text(), nullable=False),
            sa.Column('api_secret_encrypted', sa.Text(), nullable=False),
            sa.Column('passphrase_encrypted', sa.Text(), nullable=True),
            sa.Column('permissions', sa.String(length=120), nullable=False, server_default='trade_only'),
            sa.Column('dry_run', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('user_id', 'exchange', 'account_label', name='uq_user_exchange_label'),
        )

    account_indexes = {index['name'] for index in sa.inspect(bind).get_indexes('user_exchange_accounts')}
    if 'ix_user_exchange_accounts_user_id' not in account_indexes:
        op.create_index('ix_user_exchange_accounts_user_id', 'user_exchange_accounts', ['user_id'])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if 'user_exchange_accounts' in tables:
        account_indexes = {index['name'] for index in sa.inspect(bind).get_indexes('user_exchange_accounts')}
        if 'ix_user_exchange_accounts_user_id' in account_indexes:
            op.drop_index('ix_user_exchange_accounts_user_id', table_name='user_exchange_accounts')
        op.drop_table('user_exchange_accounts')
    if 'users' in tables:
        user_indexes = {index['name'] for index in sa.inspect(bind).get_indexes('users')}
        if 'ix_users_email' in user_indexes:
            op.drop_index('ix_users_email', table_name='users')
        op.drop_table('users')
