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
    timestamp = decision.timestamp.strftime('%H:%M')
    return AiLogResponse(
        time=timestamp,
        message=decision.reason,
        severity=_severity_for_decision(decision.decision_type),
        detail=decision.explanation,
    )


async def get_ai_logs(db: AsyncSession, limit: int = 50) -> list[AiLogResponse]:
    decisions = await get_ai_decisions(db, limit=limit)
    return [decision_to_log(decision) for decision in decisions]
