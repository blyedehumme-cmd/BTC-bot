from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import PaperTradeCreate, PaperTradeResponse
from app.services.trade_repository import create_paper_trade, get_paper_trades

router = APIRouter()


@router.get('/', response_model=list[PaperTradeResponse])
async def list_paper_trades(db: AsyncSession = Depends(get_db)):
    return await get_paper_trades(db)


@router.post('/', response_model=PaperTradeResponse)
async def add_paper_trade(trade: PaperTradeCreate, db: AsyncSession = Depends(get_db)):
    return await create_paper_trade(db, trade)
