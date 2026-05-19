from fastapi import APIRouter
from app.services.db_init import init_db

router = APIRouter()

@router.post('/init')
async def initialize_database():
    await init_db()
    return {'status': 'ok', 'message': 'Database initialized successfully.'}
