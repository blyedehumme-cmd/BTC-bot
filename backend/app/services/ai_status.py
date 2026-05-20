from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Signal


def _risk_level_from_confidence(confidence: int) -> str:
    if confidence >= 80:
        return 'Low'
    if confidence >= 50:
        return 'Medium'
    if confidence > 0:
        return 'High'
    return 'Unknown'


async def get_ai_status(db: AsyncSession) -> dict[str, object]:
    latest_signal = await db.scalar(select(Signal).order_by(Signal.created_at.desc()).limit(1))
    last_signal = 'No signal generated yet.'
    confidence = 0
    risk_level = 'Unknown'
    last_analysis_time = datetime.utcnow().isoformat() + 'Z'
    if latest_signal:
        last_signal = f"{latest_signal.direction} ({latest_signal.timeframe})"
        confidence = latest_signal.confidence_score
        risk_level = getattr(latest_signal, 'risk_level', None) or _risk_level_from_confidence(confidence)
        last_analysis_time = latest_signal.created_at.isoformat() + 'Z'

    return {
        'engine_status': 'Online',
        'mode': 'PAPER_TRADING',
        'last_signal': last_signal,
        'confidence': int(confidence),
        'risk_level': risk_level,
        'last_analysis_time': last_analysis_time,
        'backend_connected': True,
    }
