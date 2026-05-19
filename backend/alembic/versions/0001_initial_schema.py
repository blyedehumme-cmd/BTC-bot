"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-05-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('timeframe', sa.String(length=16), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('confidence_score', sa.Integer(), nullable=False),
        sa.Column('risk_level', sa.String(length=32), nullable=False),
        sa.Column('market_condition', sa.String(length=64), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'trades_paper',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('closed_price', sa.Float(), nullable=True),
        sa.Column('result_pct', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('drawdown_pct', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    op.create_table(
        'ai_decisions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('decision_type', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('condition_snapshot', sa.Text(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'market_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('timeframe', sa.String(length=16), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('trend', sa.String(length=32), nullable=False),
        sa.Column('support', sa.Float(), nullable=False),
        sa.Column('resistance', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('indicators', sa.Text(), nullable=True),
        sa.Column('pattern_analysis', sa.Text(), nullable=True),
    )

    op.create_table(
        'strategy_performance',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('timeframe', sa.String(length=16), nullable=False),
        sa.Column('total_signals', sa.Integer(), nullable=False),
        sa.Column('wins', sa.Integer(), nullable=False),
        sa.Column('losses', sa.Integer(), nullable=False),
        sa.Column('win_rate', sa.Float(), nullable=False),
        sa.Column('average_return', sa.Float(), nullable=False),
        sa.Column('max_drawdown', sa.Float(), nullable=False),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'rejected_signals',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('reject_reason', sa.Text(), nullable=False),
        sa.Column('rejection_score', sa.Integer(), nullable=False),
        sa.Column('conditions', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'learning_notes',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('metric', sa.String(length=64), nullable=False),
        sa.Column('observation', sa.Text(), nullable=False),
        sa.Column('improvement_action', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('learning_notes')
    op.drop_table('rejected_signals')
    op.drop_table('strategy_performance')
    op.drop_table('market_snapshots')
    op.drop_table('ai_decisions')
    op.drop_table('trades_paper')
    op.drop_table('signals')
