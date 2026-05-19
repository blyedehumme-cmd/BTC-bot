from fastapi import APIRouter
from .ai import router as ai_router
from .health import router as health_router
from .logs import router as logs_router
from .market import router as market_router
from .signals import router as signals_router

api_router = APIRouter()
api_router.include_router(health_router, prefix='/health', tags=['health'])
api_router.include_router(signals_router, prefix='/signals', tags=['signals'])
api_router.include_router(logs_router, prefix='/logs', tags=['logs'])
api_router.include_router(market_router, prefix='/market', tags=['market'])
api_router.include_router(ai_router, prefix='/ai', tags=['ai'])
