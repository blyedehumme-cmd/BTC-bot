from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import BotControlResponse
from app.services.bot_control import get_bot_control, set_bot_active

router = APIRouter()


@router.get('/status', response_model=BotControlResponse)
@router.get('/status/', response_model=BotControlResponse)
async def bot_status(db: AsyncSession = Depends(get_db)):
    return await get_bot_control(db)


@router.post('/start', response_model=BotControlResponse)
@router.post('/start/', response_model=BotControlResponse)
async def start_bot(db: AsyncSession = Depends(get_db)):
    return await set_bot_active(db, True)


@router.post('/stop', response_model=BotControlResponse)
@router.post('/stop/', response_model=BotControlResponse)
async def stop_bot(db: AsyncSession = Depends(get_db)):
    return await set_bot_active(db, False)
