from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import MarketSnapshotResponse
from app.services.market_repository import get_market_snapshots

router = APIRouter()


@router.get('/snapshots', response_model=list[MarketSnapshotResponse])
async def list_market_snapshots(db: AsyncSession = Depends(get_db)):
    return await get_market_snapshots(db)
