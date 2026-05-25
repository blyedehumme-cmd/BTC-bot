from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MarketSnapshot
from app.schemas.schemas import MarketSnapshotCreate
from app.utils.datetime import utc_naive


async def get_market_snapshots(db: AsyncSession) -> Sequence[MarketSnapshot]:
    result = await db.execute(select(MarketSnapshot).order_by(MarketSnapshot.updated_at.desc()))
    return result.scalars().all()


async def create_market_snapshot(db: AsyncSession, payload: MarketSnapshotCreate) -> MarketSnapshot:
    snapshot = MarketSnapshot(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        price=payload.price,
        trend=payload.trend,
        support=payload.support,
        resistance=payload.resistance,
        volume=payload.volume,
        updated_at=utc_naive(payload.updated_at),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
