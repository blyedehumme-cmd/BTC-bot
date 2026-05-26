from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    User,
    UserBotEvent,
    UserBotSettings,
    UserExchangeAccount,
    UserPaperAccount,
    UserPaperPosition,
)
from app.schemas.schemas import (
    UserBotEventResponse,
    UserBotSettingsResponse,
    UserPaperAccountResponse,
    UserPaperPositionResponse,
    UserPaperRuntimeResponse,
)


async def get_or_create_user_paper_account(
    user: User,
    settings: UserBotSettings,
    db: AsyncSession,
) -> UserPaperAccount:
    result = await db.execute(select(UserPaperAccount).where(UserPaperAccount.user_id == user.id))
    account = result.scalar_one_or_none()
    if account is not None:
        return account

    now = datetime.utcnow()
    starting_balance = float(settings.paper_balance or 5000.0)
    account = UserPaperAccount(
        user_id=user.id,
        starting_balance=starting_balance,
        cash_balance=starting_balance,
        equity=starting_balance,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        margin_reserved=0.0,
        open_notional=0.0,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    await log_user_event(
        user=user,
        db=db,
        event_type='paper_account_created',
        severity='info',
        message='Cuenta paper creada para este usuario.',
        payload={'starting_balance': starting_balance},
        commit=True,
    )
    return account


async def log_user_event(
    user: User,
    db: AsyncSession,
    event_type: str,
    message: str,
    severity: str = 'info',
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> UserBotEvent:
    event = UserBotEvent(
        user_id=user.id,
        event_type=event_type,
        severity=severity,
        message=message,
        detail=detail,
        payload=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    if commit:
        await db.commit()
        await db.refresh(event)
    return event


async def reset_user_paper_runtime(user: User, settings: UserBotSettings, db: AsyncSession) -> UserPaperAccount:
    await db.execute(delete(UserPaperPosition).where(UserPaperPosition.user_id == user.id))
    await db.execute(delete(UserBotEvent).where(UserBotEvent.user_id == user.id))

    result = await db.execute(select(UserPaperAccount).where(UserPaperAccount.user_id == user.id))
    account = result.scalar_one_or_none()
    now = datetime.utcnow()
    starting_balance = float(settings.paper_balance or 5000.0)
    if account is None:
        account = UserPaperAccount(
            user_id=user.id,
            starting_balance=starting_balance,
            cash_balance=starting_balance,
            equity=starting_balance,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            margin_reserved=0.0,
            open_notional=0.0,
            created_at=now,
            updated_at=now,
        )
        db.add(account)
    else:
        account.starting_balance = starting_balance
        account.cash_balance = starting_balance
        account.equity = starting_balance
        account.realized_pnl = 0.0
        account.unrealized_pnl = 0.0
        account.margin_reserved = 0.0
        account.open_notional = 0.0
        account.updated_at = now

    await log_user_event(
        user=user,
        db=db,
        event_type='paper_runtime_reset',
        severity='warning',
        message='Runtime paper reiniciado para este usuario.',
        payload={'starting_balance': starting_balance},
    )
    await db.commit()
    await db.refresh(account)
    return account


async def build_user_runtime_snapshot(
    user: User,
    settings: UserBotSettings,
    db: AsyncSession,
) -> UserPaperRuntimeResponse:
    account = await get_or_create_user_paper_account(user, settings, db)
    positions_result = await db.execute(
        select(UserPaperPosition)
        .where(UserPaperPosition.user_id == user.id, UserPaperPosition.status == 'OPEN')
        .order_by(UserPaperPosition.opened_at.desc())
    )
    open_positions = positions_result.scalars().all()

    events_result = await db.execute(
        select(UserBotEvent)
        .where(UserBotEvent.user_id == user.id)
        .order_by(UserBotEvent.created_at.desc())
        .limit(12)
    )
    latest_events = events_result.scalars().all()

    exchange_result = await db.execute(
        select(UserExchangeAccount).where(
            UserExchangeAccount.user_id == user.id,
            UserExchangeAccount.exchange == settings.selected_exchange,
            UserExchangeAccount.is_active.is_(True),
            UserExchangeAccount.dry_run.is_(True),
        )
    )
    exchange_ready = exchange_result.scalar_one_or_none() is not None
    active_symbols = [symbol.strip().upper() for symbol in settings.symbols.split(',') if symbol.strip()]

    return UserPaperRuntimeResponse(
        account=UserPaperAccountResponse(
            starting_balance=account.starting_balance,
            cash_balance=account.cash_balance,
            equity=account.equity,
            realized_pnl=account.realized_pnl,
            unrealized_pnl=account.unrealized_pnl,
            margin_reserved=account.margin_reserved,
            open_notional=account.open_notional,
            updated_at=account.updated_at,
        ),
        open_positions=[
            UserPaperPositionResponse(
                id=position.id,
                symbol=position.symbol,
                side=position.side,
                timeframe=position.timeframe,
                entry_price=position.entry_price,
                mark_price=position.mark_price,
                size=position.size,
                notional=position.notional,
                margin_reserved=position.margin_reserved,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                leverage=position.leverage,
                status=position.status,
                opened_at=position.opened_at,
                updated_at=position.updated_at,
            )
            for position in open_positions
        ],
        latest_events=[
            UserBotEventResponse(
                id=event.id,
                event_type=event.event_type,
                severity=event.severity,
                message=event.message,
                detail=event.detail,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in latest_events
        ],
        bot_settings=UserBotSettingsResponse(
            active=settings.active,
            mode=settings.mode,
            selected_exchange=settings.selected_exchange,
            symbols=settings.symbols,
            paper_balance=settings.paper_balance,
            max_open_positions=settings.max_open_positions,
            risk_profile=settings.risk_profile,
            updated_at=settings.updated_at,
        ),
        exchange_ready=exchange_ready,
        active_exchange=settings.selected_exchange,
        active_symbols=active_symbols,
        open_positions_count=len(open_positions),
        max_open_positions=settings.max_open_positions,
    )
