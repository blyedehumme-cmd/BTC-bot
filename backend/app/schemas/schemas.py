from datetime import datetime
from pydantic import BaseModel


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
    created_at: datetime | None = None


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
    message: str
    severity: str | None = None
    detail: str | None = None


class AiStatusResponse(BaseModel):
    engine_status: str
    mode: str
    last_signal: str
    confidence: int
    risk_level: str
    last_analysis_time: str
    backend_connected: bool


class StrategyPerformanceResponse(BaseModel):
    total_signals: int
    wins: int
    losses: int
    win_rate: int
    average_return: float
    max_drawdown: float


class MarketLiveResponse(BaseModel):
    symbol: str
    price: float
    change_1h_pct: float
    signal: str
    confidence: int
    support: float
    resistance: float
    trend: str
    updated_at: str
    backend_connected: bool


class PaperTradeBase(BaseModel):
    signal_id: int
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    target_price: float | None = None
    closed_price: float | None = None
    result_pct: float | None = None
    status: str
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    drawdown_pct: float | None = None
    notes: str | None = None


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
    updated_at: str

    model_config = {
        'from_attributes': True,
    }
