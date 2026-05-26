"""user paper runtime

Revision ID: 0005_user_paper_runtime
Revises: 0004_user_bot_settings
Create Date: 2026-05-26 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '0005_user_paper_runtime'
down_revision = '0004_user_bot_settings'
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    tables = _table_names()
    if 'user_paper_accounts' not in tables:
        op.create_table(
            'user_paper_accounts',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('starting_balance', sa.Float(), nullable=False, server_default='5000'),
            sa.Column('cash_balance', sa.Float(), nullable=False, server_default='5000'),
            sa.Column('equity', sa.Float(), nullable=False, server_default='5000'),
            sa.Column('realized_pnl', sa.Float(), nullable=False, server_default='0'),
            sa.Column('unrealized_pnl', sa.Float(), nullable=False, server_default='0'),
            sa.Column('margin_reserved', sa.Float(), nullable=False, server_default='0'),
            sa.Column('open_notional', sa.Float(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_user_paper_accounts_user_id', 'user_paper_accounts', ['user_id'], unique=True)

    if 'user_paper_positions' not in tables:
        op.create_table(
            'user_paper_positions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('symbol', sa.String(length=24), nullable=False),
            sa.Column('side', sa.String(length=16), nullable=False),
            sa.Column('timeframe', sa.String(length=16), nullable=False),
            sa.Column('entry_price', sa.Float(), nullable=False),
            sa.Column('mark_price', sa.Float(), nullable=False),
            sa.Column('size', sa.Float(), nullable=False),
            sa.Column('notional', sa.Float(), nullable=False),
            sa.Column('margin_reserved', sa.Float(), nullable=False),
            sa.Column('stop_loss', sa.Float(), nullable=True),
            sa.Column('take_profit', sa.Float(), nullable=True),
            sa.Column('leverage', sa.Float(), nullable=False, server_default='1'),
            sa.Column('status', sa.String(length=24), nullable=False, server_default='OPEN'),
            sa.Column('opened_at', sa.DateTime(), nullable=False),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.Column('close_reason', sa.String(length=80), nullable=True),
            sa.Column('realized_pnl', sa.Float(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_user_paper_positions_user_id', 'user_paper_positions', ['user_id'])
        op.create_index('ix_user_paper_positions_symbol', 'user_paper_positions', ['symbol'])

    if 'user_bot_events' not in tables:
        op.create_table(
            'user_bot_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('severity', sa.String(length=24), nullable=False, server_default='info'),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('payload', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_user_bot_events_user_id', 'user_bot_events', ['user_id'])
        op.create_index('ix_user_bot_events_created_at', 'user_bot_events', ['created_at'])

    # If a previous deploy partially created tables, make sure key indexes exist.
    if 'user_paper_accounts' in _table_names() and 'ix_user_paper_accounts_user_id' not in _index_names('user_paper_accounts'):
        op.create_index('ix_user_paper_accounts_user_id', 'user_paper_accounts', ['user_id'], unique=True)
    if 'user_paper_positions' in _table_names():
        indexes = _index_names('user_paper_positions')
        if 'ix_user_paper_positions_user_id' not in indexes:
            op.create_index('ix_user_paper_positions_user_id', 'user_paper_positions', ['user_id'])
        if 'ix_user_paper_positions_symbol' not in indexes:
            op.create_index('ix_user_paper_positions_symbol', 'user_paper_positions', ['symbol'])
    if 'user_bot_events' in _table_names():
        indexes = _index_names('user_bot_events')
        if 'ix_user_bot_events_user_id' not in indexes:
            op.create_index('ix_user_bot_events_user_id', 'user_bot_events', ['user_id'])
        if 'ix_user_bot_events_created_at' not in indexes:
            op.create_index('ix_user_bot_events_created_at', 'user_bot_events', ['created_at'])


def downgrade() -> None:
    tables = _table_names()
    if 'user_bot_events' in tables:
        for index in ('ix_user_bot_events_created_at', 'ix_user_bot_events_user_id'):
            if index in _index_names('user_bot_events'):
                op.drop_index(index, table_name='user_bot_events')
        op.drop_table('user_bot_events')
    if 'user_paper_positions' in tables:
        for index in ('ix_user_paper_positions_symbol', 'ix_user_paper_positions_user_id'):
            if index in _index_names('user_paper_positions'):
                op.drop_index(index, table_name='user_paper_positions')
        op.drop_table('user_paper_positions')
    if 'user_paper_accounts' in tables:
        if 'ix_user_paper_accounts_user_id' in _index_names('user_paper_accounts'):
            op.drop_index('ix_user_paper_accounts_user_id', table_name='user_paper_accounts')
        op.drop_table('user_paper_accounts')
