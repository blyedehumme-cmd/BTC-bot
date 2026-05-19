from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.database import get_db

router = APIRouter()


@router.get('/')
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = 'connected'
    try:
        await db.execute(text('SELECT 1'))
    except Exception as exc:
        db_status = f'error: {exc}'

    return {
        'status': 'healthy' if db_status == 'connected' else 'degraded',
        'mode': 'paper_trading',
        'environment': settings.environment,
        'database': db_status,
        'message': 'Backend is running in paper trading mode only.',
    }
