from fastapi import APIRouter
from app.schemas.schemas import AiStatusResponse, StrategyPerformanceResponse
from app.services.ai_status import get_ai_status
from app.services.performance import get_performance_summary

router = APIRouter()


@router.get('/status', response_model=AiStatusResponse)
async def ai_status():
    return get_ai_status()


@router.get('/performance', response_model=StrategyPerformanceResponse)
async def ai_performance():
    return get_performance_summary()
