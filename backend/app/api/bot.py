from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.schemas.schemas import BotControlResponse, WorkerRuntimeResponse
from app.services.bot_control import get_bot_control, request_manual_close, request_stop_loss_update, set_bot_active
from app.services.user_runtime import build_worker_runtime

router = APIRouter()


class ManualCloseRequest(BaseModel):
    symbol: str


class StopLossUpdateRequest(BaseModel):
    symbol: str
    stop_loss: float


@router.get('/status', response_model=BotControlResponse)
@router.get('/status/', response_model=BotControlResponse)
async def bot_status(db: AsyncSession = Depends(get_db)):
    return await get_bot_control(db)


@router.get('/worker-runtime', response_model=WorkerRuntimeResponse)
@router.get('/worker-runtime/', response_model=WorkerRuntimeResponse)
async def worker_runtime(db: AsyncSession = Depends(get_db)):
    return await build_worker_runtime(db)


@router.post('/start', response_model=BotControlResponse)
@router.post('/start/', response_model=BotControlResponse)
async def start_bot(db: AsyncSession = Depends(get_db)):
    return await set_bot_active(db, True)


@router.post('/stop', response_model=BotControlResponse)
@router.post('/stop/', response_model=BotControlResponse)
async def stop_bot(db: AsyncSession = Depends(get_db)):
    return await set_bot_active(db, False)


@router.post('/close-position')
@router.post('/close-position/')
async def close_position(payload: ManualCloseRequest, db: AsyncSession = Depends(get_db)):
    return await request_manual_close(db, payload.symbol)


@router.post('/update-stop-loss')
@router.post('/update-stop-loss/')
async def update_stop_loss(payload: StopLossUpdateRequest, db: AsyncSession = Depends(get_db)):
    return await request_stop_loss_update(db, payload.symbol, payload.stop_loss)
