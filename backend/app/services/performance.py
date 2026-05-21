from __future__ import annotations

from collections import defaultdict

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
    trade_result = await db.execute(select(PaperTrade).order_by(PaperTrade.opened_at.asc()))
    trades = trade_result.scalars().all()
    equity = 0.0
    equity_peak = 0.0
    max_equity_drawdown = 0.0
    equity_curve = []
    monthly: dict[str, dict[str, object]] = defaultdict(lambda: {'month': '', 'trades': 0, 'wins': 0, 'losses': 0, 'pnl_pct': 0.0})

    for trade in trades:
        result_pct = float(trade.result_pct or 0.0)
        equity += result_pct
        equity_peak = max(equity_peak, equity)
        max_equity_drawdown = max(max_equity_drawdown, equity_peak - equity)
        event_time = trade.closed_at or trade.opened_at
        equity_curve.append({
            'time': event_time.isoformat() + 'Z',
            'equity': round(equity, 4),
            'trade_id': trade.id,
            'result_pct': result_pct,
        })
        month_key = event_time.strftime('%Y-%m')
        row = monthly[month_key]
        row['month'] = month_key
        row['trades'] = int(row['trades']) + 1
        row['pnl_pct'] = float(row['pnl_pct']) + result_pct
        if result_pct > 0:
            row['wins'] = int(row['wins']) + 1
        else:
            row['losses'] = int(row['losses']) + 1

    monthly_stats = []
    for row in sorted(monthly.values(), key=lambda item: str(item['month']), reverse=True):
        row_trades = int(row['trades'])
        row_wins = int(row['wins'])
        monthly_stats.append({
            **row,
            'pnl_pct': round(float(row['pnl_pct']), 4),
            'win_rate': int(round(row_wins / row_trades * 100)) if row_trades else 0,
        })

    return {
        'total_trades': int(total_trades),
        'total_signals': int(total_signals),
        'wins': int(wins),
        'losses': int(losses),
        'win_rate': win_rate,
        'average_return': float(avg_return),
        'max_drawdown': float(max(max_drawdown, max_equity_drawdown)),
        'equity_curve': equity_curve[-80:],
        'monthly_stats': monthly_stats[:12],
    }
