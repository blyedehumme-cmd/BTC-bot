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
        confidence_score=0,
        risk_level='Unknown',
        market_condition='Pending',
        approved=False,
        explanation='Pending evaluation in paper trading mode.',
        created_at=datetime.utcnow(),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal
