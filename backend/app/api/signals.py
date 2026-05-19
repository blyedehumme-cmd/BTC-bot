from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import SignalCreate, SignalResponse
from app.services.signal_repository import create_signal, get_signals

router = APIRouter()


@router.get('/', response_model=list[SignalResponse])
async def list_signals(db: AsyncSession = Depends(get_db)):
    return await get_signals(db)


@router.post('/', response_model=SignalResponse)
async def add_signal(signal: SignalCreate, db: AsyncSession = Depends(get_db)):
    return await create_signal(db, signal)
