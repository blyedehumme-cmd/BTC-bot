from datetime import datetime
from pydantic import BaseModel


class SignalBase(BaseModel):
    symbol: str
    timeframe: str
    direction: str


class SignalCreate(SignalBase):
    pass


class SignalResponse(SignalBase):
    id: int
    confidence_score: int
    risk_level: str
    market_condition: str
    approved: bool
    explanation: str
    created_at: datetime

    class Config:
        orm_mode = True


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


class MarketSnapshotResponse(BaseModel):
    symbol: str
    timeframe: str
    price: float
    trend: str
    support: float
    resistance: float
    volume: float
    updated_at: str
