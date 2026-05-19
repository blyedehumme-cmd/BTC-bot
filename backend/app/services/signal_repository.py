from datetime import datetime
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Signal
from app.schemas.schemas import SignalCreate


async def get_signals(db: AsyncSession) -> Sequence[Signal]:
    result = await db.execute(select(Signal).order_by(Signal.created_at.desc()))
    return result.scalars().all()


async def create_signal(db: AsyncSession, payload: SignalCreate) -> Signal:
    signal = Signal(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        direction=payload.direction,
        confidence_score=payload.confidence_score,
        risk_level=payload.risk_level,
        market_condition=payload.market_condition,
        approved=payload.approved,
        explanation=payload.explanation,
        created_at=payload.created_at or datetime.utcnow(),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal
