from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Signal


async def get_performance_summary(db: AsyncSession) -> dict[str, object]:
    total_signals = await db.scalar(select(func.count()).select_from(Signal)) or 0
    approved_signals = await db.scalar(select(func.count()).select_from(Signal).where(Signal.approved.is_(True))) or 0
    rejected_signals = total_signals - approved_signals
    win_rate = int(round((approved_signals / total_signals * 100))) if total_signals else 0
    return {
        'total_signals': int(total_signals),
        'wins': int(approved_signals),
        'losses': int(rejected_signals),
        'win_rate': win_rate,
        'average_return': 0.0,
        'max_drawdown': 0.0,
    }
