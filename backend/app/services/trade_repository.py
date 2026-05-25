from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import PaperTrade
from app.schemas.schemas import PaperTradeCreate
from app.utils.datetime import utc_naive


async def get_paper_trades(db: AsyncSession) -> Sequence[PaperTrade]:
    result = await db.execute(select(PaperTrade).order_by(PaperTrade.opened_at.desc()))
    return result.scalars().all()


async def create_paper_trade(db: AsyncSession, payload: PaperTradeCreate) -> PaperTrade:
    trade = PaperTrade(
        signal_id=payload.signal_id,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        target_price=payload.target_price,
        closed_price=payload.closed_price,
        result_pct=payload.result_pct,
        status=payload.status,
        opened_at=utc_naive(payload.opened_at) or datetime.utcnow(),
        closed_at=utc_naive(payload.closed_at),
        drawdown_pct=payload.drawdown_pct,
        notes=payload.notes,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return trade
