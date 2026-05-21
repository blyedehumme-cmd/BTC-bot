from __future__ import annotations

import logging
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
