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
    engine: str
    paper_mode: bool
    last_decision: str
    approved_signals: int
    rejected_signals: int
    risk_level: str
    explanation: str
    last_updated: str


class StrategyPerformanceResponse(BaseModel):
    total_signals: int
    wins: int
    losses: int
    win_rate: int
    average_return: float
    max_drawdown: float


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
