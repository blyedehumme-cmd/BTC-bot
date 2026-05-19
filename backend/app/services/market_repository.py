from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MarketSnapshot


async def get_market_snapshots(db: AsyncSession) -> Sequence[MarketSnapshot]:
    result = await db.execute(select(MarketSnapshot).order_by(MarketSnapshot.created_at.desc()))
    return result.scalars().all()
