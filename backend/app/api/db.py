from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.services.db_init import init_db

router = APIRouter()


@router.post('/init')
async def initialize_database():
    if settings.is_production:
        raise HTTPException(status_code=403, detail='Database init endpoint disabled in production.')
    await init_db()
    return {'status': 'ok', 'message': 'Database initialized successfully.'}
