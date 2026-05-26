from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SignalBase(BaseModel):
    symbol: str
    timeframe: str
    direction: str


class SignalCreate(SignalBase):
    confidence_score: int = 0
    risk_level: str = 'Unknown'
    market_condition: str = 'Pending'
    approved: bool = False
    explanation: str = 'Pending evaluation in paper trading mode.'
    created_at: Optional[datetime] = None


class SignalResponse(SignalBase):
    id: int
    confidence_score: int
    risk_level: str
    market_condition: str
    approved: bool
    explanation: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class AiLogResponse(BaseModel):
    time: str
    timestamp: Optional[str] = None
    message: str
    severity: Optional[str] = None
    detail: Optional[str] = None
    condition_snapshot: Optional[str] = None


class AiStatusResponse(BaseModel):
    engine_status: str
    mode: str
    last_signal: str
    confidence: int
    risk_level: str
    last_analysis_time: str
    backend_connected: bool


class AiDecisionCreate(BaseModel):
    signal_id: int = 0
    decision_type: str
    reason: str
    condition_snapshot: Optional[str] = None
    explanation: str
    timestamp: Optional[datetime] = None


class AiDecisionResponse(BaseModel):
    id: int
    signal_id: int
    decision_type: str
    reason: str
    condition_snapshot: Optional[str] = None
    explanation: str
    timestamp: datetime

    model_config = {
        'from_attributes': True,
    }


class StrategyPerformanceResponse(BaseModel):
    total_trades: int
    total_signals: Optional[int] = None
    wins: int
    losses: int
    win_rate: int
    average_return: float
    max_drawdown: float
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    monthly_stats: List[Dict[str, Any]] = Field(default_factory=list)


class MarketLiveResponse(BaseModel):
    symbol: str
    asset: Optional[str] = None
    asset_name: Optional[str] = None
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    price: float
    change_1h_pct: float
    signal: str
    confidence: int
    support: float
    resistance: float
    trend: str
    adx: Optional[float] = None
    atr: Optional[float] = None
    volume: Optional[float] = None
    volume_ratio: Optional[float] = None
    candles: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: str
    backend_connected: bool


class PaperTradeBase(BaseModel):
    signal_id: int
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    target_price: Optional[float] = None
    closed_price: Optional[float] = None
    result_pct: Optional[float] = None
    status: str
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    drawdown_pct: Optional[float] = None
    notes: Optional[str] = None


class PaperTradeCreate(PaperTradeBase):
    pass


class PaperTradeResponse(PaperTradeBase):
    id: int

    model_config = {
        'from_attributes': True,
    }


class MarketSnapshotCreate(BaseModel):
    symbol: str
    timeframe: str
    price: float
    trend: str
    support: float
    resistance: float
    volume: float
    updated_at: datetime


class MarketSnapshotResponse(BaseModel):
    symbol: str
    timeframe: str
    price: float
    trend: str
    support: float
    resistance: float
    volume: float
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class BotControlResponse(BaseModel):
    active: bool
    mode: str
    updated_at: str
    updated_by: str
    note: Optional[str] = None


class UserRegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    paper_trading: bool
    is_active: bool
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserResponse


class ExchangeAccountCreate(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    account_label: str = 'main'
    dry_run: bool = True


class ExchangeAccountResponse(BaseModel):
    id: int
    exchange: str
    account_label: str
    permissions: str
    dry_run: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    api_key_preview: str
    has_secret: bool
    has_passphrase: bool


class UserBotSettingsUpdate(BaseModel):
    active: Optional[bool] = None
    selected_exchange: Optional[str] = None
    symbols: Optional[str] = None
    paper_balance: Optional[float] = None
    max_open_positions: Optional[int] = None
    risk_profile: Optional[str] = None


class UserBotSettingsResponse(BaseModel):
    active: bool
    mode: str
    selected_exchange: str
    symbols: str
    paper_balance: float
    max_open_positions: int
    risk_profile: str
    updated_at: datetime
