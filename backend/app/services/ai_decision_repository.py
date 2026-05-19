from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AiDecision
from app.schemas.schemas import AiDecisionCreate


async def get_ai_decisions(db: AsyncSession, limit: int = 50) -> Sequence[AiDecision]:
    result = await db.execute(
        select(AiDecision).order_by(AiDecision.timestamp.desc()).limit(limit)
    )
    return result.scalars().all()


async def create_ai_decision(db: AsyncSession, payload: AiDecisionCreate) -> AiDecision:
    decision = AiDecision(
        signal_id=payload.signal_id,
        decision_type=payload.decision_type,
        reason=payload.reason,
        condition_snapshot=payload.condition_snapshot,
        explanation=payload.explanation,
        timestamp=payload.timestamp or datetime.utcnow(),
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision
