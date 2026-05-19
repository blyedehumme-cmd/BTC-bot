from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import PaperTrade, Signal


async def get_performance_summary(db: AsyncSession) -> dict[str, object]:
    total_trades = await db.scalar(select(func.count()).select_from(PaperTrade)) or 0
    total_signals = await db.scalar(select(func.count()).select_from(Signal)) or 0
    wins = await db.scalar(select(func.count()).select_from(PaperTrade).where(PaperTrade.result_pct > 0)) or 0
    losses = await db.scalar(select(func.count()).select_from(PaperTrade).where(PaperTrade.result_pct <= 0)) or 0
    avg_return = await db.scalar(select(func.avg(PaperTrade.result_pct)).where(PaperTrade.result_pct.is_not(None))) or 0.0
    min_return = await db.scalar(select(func.min(PaperTrade.result_pct)).where(PaperTrade.result_pct.is_not(None)))
    max_drawdown = abs(min_return) if min_return is not None and min_return < 0 else 0.0
    win_rate = int(round((wins / total_trades * 100))) if total_trades else 0
    return {
        'total_trades': int(total_trades),
        'total_signals': int(total_signals),
        'wins': int(wins),
        'losses': int(losses),
        'win_rate': win_rate,
        'average_return': float(avg_return),
        'max_drawdown': float(max_drawdown),
    }
