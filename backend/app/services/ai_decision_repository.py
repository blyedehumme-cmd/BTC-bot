from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AiDecision
from app.schemas.schemas import AiDecisionCreate
from app.services.user_runtime import sync_global_worker_decision_to_user_runtime
from app.utils.datetime import utc_naive


async def get_ai_decisions(db: AsyncSession, limit: int = 50) -> Sequence[AiDecision]:
    result = await db.execute(
        select(AiDecision).order_by(AiDecision.timestamp.desc()).limit(limit)
    )
    return result.scalars().all()


async def create_ai_decision(db: AsyncSession, payload: AiDecisionCreate) -> AiDecision:
    timestamp = utc_naive(payload.timestamp) or datetime.utcnow()
    decision = AiDecision(
        signal_id=payload.signal_id,
        decision_type=payload.decision_type,
        reason=payload.reason,
        condition_snapshot=payload.condition_snapshot,
        explanation=payload.explanation,
        timestamp=timestamp,
    )
    db.add(decision)
    await sync_global_worker_decision_to_user_runtime(
        db=db,
        decision_type=payload.decision_type,
        condition_snapshot=payload.condition_snapshot,
        reason=payload.reason,
        explanation=payload.explanation,
    )
    await db.commit()
    await db.refresh(decision)
    return decision
