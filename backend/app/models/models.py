from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Signal(Base):
    __tablename__ = 'signals'

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(length=32), nullable=False)
    timeframe = Column(String(length=16), nullable=False)
    direction = Column(String(length=16), nullable=False)
    confidence_score = Column(Integer, nullable=False)
    risk_level = Column(String(length=32), nullable=False)
    market_condition = Column(String(length=64), nullable=False)
    approved = Column(Boolean, default=False)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class PaperTrade(Base):
    __tablename__ = 'trades_paper'

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    closed_price = Column(Float, nullable=True)
    result_pct = Column(Float, nullable=True)
    status = Column(String(length=32), nullable=False)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    drawdown_pct = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)


class AiDecision(Base):
    __tablename__ = 'ai_decisions'

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, nullable=False)
    decision_type = Column(String(length=64), nullable=False)
    reason = Column(Text, nullable=False)
    condition_snapshot = Column(Text, nullable=True)
    explanation = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)


class MarketSnapshot(Base):
    __tablename__ = 'market_snapshots'

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(length=32), nullable=False)
    timeframe = Column(String(length=16), nullable=False)
    price = Column(Float, nullable=False)
    trend = Column(String(length=32), nullable=False)
    support = Column(Float, nullable=False)
    resistance = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    indicators = Column(Text, nullable=True)
    pattern_analysis = Column(Text, nullable=True)


class StrategyPerformance(Base):
    __tablename__ = 'strategy_performance'

    id = Column(Integer, primary_key=True, index=True)
    timeframe = Column(String(length=16), nullable=False)
    total_signals = Column(Integer, nullable=False)
    wins = Column(Integer, nullable=False)
    losses = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=False)
    average_return = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=False)
    last_updated = Column(DateTime, nullable=False)


class RejectedSignal(Base):
    __tablename__ = 'rejected_signals'

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, nullable=False)
    reject_reason = Column(Text, nullable=False)
    rejection_score = Column(Integer, nullable=False)
    conditions = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False)


class LearningNote(Base):
    __tablename__ = 'learning_notes'

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, nullable=False)
    metric = Column(String(length=64), nullable=False)
    observation = Column(Text, nullable=False)
    improvement_action = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class BotControl(Base):
    __tablename__ = 'bot_control'

    id = Column(Integer, primary_key=True, index=True)
    active = Column(Boolean, nullable=False, default=True)
    mode = Column(String(length=32), nullable=False, default='DRY_RUN')
    updated_at = Column(DateTime, nullable=False)
    updated_by = Column(String(length=64), nullable=False, default='dashboard')
    note = Column(Text, nullable=True)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), nullable=False, unique=True, index=True)
    name = Column(String(length=120), nullable=False)
    password_hash = Column(String(length=255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    paper_trading = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    exchange_accounts = relationship('UserExchangeAccount', back_populates='user', cascade='all, delete-orphan')


class UserExchangeAccount(Base):
    __tablename__ = 'user_exchange_accounts'
    __table_args__ = (UniqueConstraint('user_id', 'exchange', 'account_label', name='uq_user_exchange_label'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    exchange = Column(String(length=32), nullable=False)
    account_label = Column(String(length=80), nullable=False, default='main')
    api_key_encrypted = Column(Text, nullable=False)
    api_secret_encrypted = Column(Text, nullable=False)
    passphrase_encrypted = Column(Text, nullable=True)
    permissions = Column(String(length=120), nullable=False, default='trade_only')
    dry_run = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    user = relationship('User', back_populates='exchange_accounts')
