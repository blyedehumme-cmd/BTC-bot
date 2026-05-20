import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.database import get_db

router = APIRouter()


async def _database_status(db: AsyncSession) -> str:
    try:
        await asyncio.wait_for(db.execute(text('SELECT 1')), timeout=3)
        return 'connected'
    except Exception as exc:
        return f'error: {exc}'


@router.get('')
@router.get('/')
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = await _database_status(db)

    return {
        'status': 'ok',
        'mode': 'paper_trading',
        'environment': settings.environment,
        'database': db_status,
        'database_status': 'healthy' if db_status == 'connected' else 'degraded',
        'message': 'Backend is running in paper trading mode only.',
    }
