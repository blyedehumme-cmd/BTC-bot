from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import (
    AiDecisionCreate,
    AiDecisionResponse,
    AiStatusResponse,
    StrategyPerformanceResponse,
)
from app.services.ai_decision_repository import create_ai_decision
from app.services.ai_status import get_ai_status
from app.services.performance import get_performance_summary

router = APIRouter()


@router.get('/status', response_model=AiStatusResponse)
async def ai_status(db: AsyncSession = Depends(get_db)):
    return await get_ai_status(db)


@router.get('/performance', response_model=StrategyPerformanceResponse)
async def ai_performance(db: AsyncSession = Depends(get_db)):
    return await get_performance_summary(db)


@router.post('/decisions', response_model=AiDecisionResponse)
async def add_ai_decision(decision: AiDecisionCreate, db: AsyncSession = Depends(get_db)):
    return await create_ai_decision(db, decision)
