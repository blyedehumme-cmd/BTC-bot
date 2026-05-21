from __future__ import annotations

from datetime import timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AiDecision
from app.schemas.schemas import AiLogResponse
from app.services.ai_decision_repository import get_ai_decisions


def _severity_for_decision(decision_type: str) -> str:
    normalized = decision_type.lower()
    if 'reject' in normalized or 'block' in normalized:
        return 'warning'
    if 'approve' in normalized or 'trade' in normalized:
        return 'success'
    return 'info'


def decision_to_log(decision: AiDecision) -> AiLogResponse:
    timestamp_value = decision.timestamp
    if timestamp_value.tzinfo is not None:
        timestamp = timestamp_value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    else:
        timestamp = timestamp_value.isoformat() + 'Z'
    return AiLogResponse(
        time=timestamp_value.strftime('%H:%M'),
        timestamp=timestamp,
        message=decision.reason,
        severity=_severity_for_decision(decision.decision_type),
        detail=decision.explanation,
        condition_snapshot=decision.condition_snapshot,
    )


async def get_ai_logs(db: AsyncSession, limit: int = 50) -> list[AiLogResponse]:
    decisions = await get_ai_decisions(db, limit=limit)
    return [decision_to_log(decision) for decision in decisions]
