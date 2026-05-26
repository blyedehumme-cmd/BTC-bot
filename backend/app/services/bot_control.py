from __future__ import annotations

import logging
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AiDecision, BotControl

logger = logging.getLogger(__name__)

BOT_CONTROL_ID = 1


def _response(control: BotControl) -> dict[str, object]:
    return {
        'active': control.active,
        'mode': control.mode,
        'updated_at': control.updated_at.isoformat() + 'Z',
        'updated_by': control.updated_by,
        'note': control.note,
    }


async def get_bot_control(db: AsyncSession) -> dict[str, object]:
    control = await db.get(BotControl, BOT_CONTROL_ID)
    if control is None:
        control = BotControl(
            id=BOT_CONTROL_ID,
            active=True,
            mode='DRY_RUN',
            updated_at=datetime.utcnow(),
            updated_by='system',
            note='Default bot control initialized in DRY_RUN mode.',
        )
        db.add(control)
        await db.commit()
        await db.refresh(control)
    return _response(control)


async def set_bot_active(db: AsyncSession, active: bool, updated_by: str = 'dashboard') -> dict[str, object]:
    control = await db.get(BotControl, BOT_CONTROL_ID)
    if control is None:
        control = BotControl(id=BOT_CONTROL_ID)
        db.add(control)

    control.active = active
    control.mode = 'DRY_RUN'
    control.updated_at = datetime.utcnow()
    control.updated_by = updated_by
    control.note = 'START BOT pressed: bot active for paper trading.' if active else 'STOP BOT pressed: new operations paused.'

    log = AiDecision(
        signal_id=0,
        decision_type='bot_started' if active else 'bot_stopped',
        reason='START BOT pressed from dashboard.' if active else 'STOP BOT pressed from dashboard.',
        condition_snapshot=None,
        explanation=control.note,
        timestamp=control.updated_at,
    )
    db.add(log)
    await db.commit()
    await db.refresh(control)

    logger.info('bot_control_updated active=%s updated_by=%s mode=DRY_RUN', active, updated_by)
    return _response(control)


async def request_manual_close(db: AsyncSession, symbol: str, updated_by: str = 'dashboard') -> dict[str, object]:
    normalized_symbol = symbol.strip().upper()
    now = datetime.utcnow()
    snapshot = {
        'action': 'close_position',
        'symbol': normalized_symbol,
        'requested_at': now.isoformat() + 'Z',
        'source': updated_by,
    }
    log = AiDecision(
        signal_id=0,
        decision_type='manual_close_request',
        reason=f'Manual close requested for {normalized_symbol}.',
        condition_snapshot=json.dumps(snapshot),
        explanation=f'Dashboard requested paper position close for {normalized_symbol} at live market price.',
        timestamp=now,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    logger.info('manual_close_requested symbol=%s updated_by=%s', normalized_symbol, updated_by)
    return {
        'accepted': True,
        'symbol': normalized_symbol,
        'requested_at': now.isoformat() + 'Z',
        'message': f'Manual close requested for {normalized_symbol}.',
    }


async def request_stop_loss_update(db: AsyncSession, symbol: str, stop_loss: float, updated_by: str = 'dashboard') -> dict[str, object]:
    normalized_symbol = symbol.strip().upper()
    if stop_loss <= 0:
        return {
            'accepted': False,
            'symbol': normalized_symbol,
            'requested_at': datetime.utcnow().isoformat() + 'Z',
            'message': 'Stop loss must be greater than 0.',
        }
    now = datetime.utcnow()
    snapshot = {
        'action': 'update_stop_loss',
        'symbol': normalized_symbol,
        'stop_loss': float(stop_loss),
        'requested_at': now.isoformat() + 'Z',
        'source': updated_by,
    }
    log = AiDecision(
        signal_id=0,
        decision_type='stop_loss_update_request',
        reason=f'Stop loss update requested for {normalized_symbol}: {stop_loss:.2f}.',
        condition_snapshot=json.dumps(snapshot),
        explanation=f'Dashboard requested paper stop loss update for {normalized_symbol} to {stop_loss:.2f}.',
        timestamp=now,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    logger.info('stop_loss_update_requested symbol=%s stop_loss=%.2f updated_by=%s', normalized_symbol, stop_loss, updated_by)
    return {
        'accepted': True,
        'symbol': normalized_symbol,
        'stop_loss': float(stop_loss),
        'requested_at': now.isoformat() + 'Z',
        'message': f'Stop loss update requested for {normalized_symbol}.',
    }
