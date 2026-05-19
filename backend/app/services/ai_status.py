from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Signal


async def get_ai_status(db: AsyncSession) -> dict[str, object]:
    total_signals = await db.scalar(select(func.count()).select_from(Signal)) or 0
    approved_signals = await db.scalar(select(func.count()).select_from(Signal).where(Signal.approved.is_(True))) or 0
    rejected_signals = total_signals - approved_signals
    latest_signal = await db.scalar(select(Signal).order_by(Signal.created_at.desc()).limit(1))
    last_decision = 'No decisions yet.'
    risk_level = 'Unknown'
    explanation = 'Awaiting paper trading signal data.'
    if latest_signal:
        last_decision = f"{latest_signal.direction} signal"
        risk_level = latest_signal.risk_level
        explanation = latest_signal.explanation
    return {
        'engine': 'Online',
        'paper_mode': True,
        'last_decision': last_decision,
        'approved_signals': int(approved_signals),
        'rejected_signals': int(rejected_signals),
        'risk_level': risk_level,
        'explanation': explanation,
        'last_updated': datetime.utcnow().isoformat() + 'Z',
    }
