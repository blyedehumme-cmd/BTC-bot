from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import AiLogResponse
from app.services.log_service import get_ai_logs

router = APIRouter()


@router.get('', response_model=list[AiLogResponse])
@router.get('/', response_model=list[AiLogResponse])
async def list_logs(db: AsyncSession = Depends(get_db)):
    return await get_ai_logs(db)
