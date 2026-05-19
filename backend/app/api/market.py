from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import MarketLiveResponse, MarketSnapshotCreate, MarketSnapshotResponse
from app.services.live_market import get_live_market_status
from app.services.market_repository import create_market_snapshot, get_market_snapshots

router = APIRouter()


@router.get('/live', response_model=MarketLiveResponse)
async def list_market_live(db: AsyncSession = Depends(get_db)):
    return await get_live_market_status(db)


@router.get('/snapshots', response_model=list[MarketSnapshotResponse])
async def list_market_snapshots(db: AsyncSession = Depends(get_db)):
    return await get_market_snapshots(db)


@router.post('/snapshots', response_model=MarketSnapshotResponse)
async def add_market_snapshot(snapshot: MarketSnapshotCreate, db: AsyncSession = Depends(get_db)):
    return await create_market_snapshot(db, snapshot)
