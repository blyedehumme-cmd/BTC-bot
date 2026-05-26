from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, exists, or_, select
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
    WorkerRuntimeResponse,
    WorkerUserProfileResponse,
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


async def select_global_worker_user(db: AsyncSession) -> tuple[User, UserBotSettings] | None:
    has_open_position = exists().where(
        UserPaperPosition.user_id == User.id,
        UserPaperPosition.status == 'OPEN',
    )
    result = await db.execute(
        select(User, UserBotSettings)
        .join(UserBotSettings, UserBotSettings.user_id == User.id)
        .where(User.is_active.is_(True), or_(UserBotSettings.active.is_(True), has_open_position))
        .order_by(UserBotSettings.updated_at.desc())
    )
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]


async def build_worker_runtime(db: AsyncSession) -> WorkerRuntimeResponse:
    has_open_position = exists().where(
        UserPaperPosition.user_id == User.id,
        UserPaperPosition.status == 'OPEN',
    )
    result = await db.execute(
        select(User, UserBotSettings)
        .join(UserBotSettings, UserBotSettings.user_id == User.id)
        .where(
            User.is_active.is_(True),
            UserBotSettings.mode == 'DRY_RUN',
            or_(UserBotSettings.active.is_(True), has_open_position),
        )
        .order_by(UserBotSettings.updated_at.desc())
    )
    profiles: list[WorkerUserProfileResponse] = []
    for user, settings in result.all():
        runtime = await build_user_runtime_snapshot(user, settings, db)
        profiles.append(
            WorkerUserProfileResponse(
                user_id=user.id,
                active=settings.active,
                mode=settings.mode,
                selected_exchange=settings.selected_exchange,
                symbols=runtime.active_symbols,
                paper_balance=settings.paper_balance,
                max_open_positions=settings.max_open_positions,
                risk_profile=settings.risk_profile,
                exchange_ready=runtime.exchange_ready,
                open_positions_count=runtime.open_positions_count,
                can_open_new_positions=bool(settings.active),
            )
        )
    return WorkerRuntimeResponse(
        active_profiles=profiles,
        active_profiles_count=len(profiles),
        worker_should_run=len(profiles) > 0,
        worker_should_open_entries=any(profile.can_open_new_positions for profile in profiles),
    )


def _safe_json_loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _normalize_worker_positions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    positions = snapshot.get('open_positions')
    if isinstance(positions, list):
        return [position for position in positions if isinstance(position, dict)]
    position = snapshot.get('open_position')
    if isinstance(position, dict) and position.get('status') == 'OPEN':
        return [position]
    return []


async def sync_global_worker_decision_to_user_runtime(
    db: AsyncSession,
    decision_type: str,
    condition_snapshot: str | None,
    reason: str,
    explanation: str,
) -> None:
    if decision_type not in {'position_status', 'position_opened'}:
        return

    selected = await select_global_worker_user(db)
    if selected is None:
        return
    user, settings = selected
    snapshot = _safe_json_loads(condition_snapshot)
    if not snapshot:
        return

    account = await get_or_create_user_paper_account(user, settings, db)
    now = datetime.utcnow()
    account.starting_balance = float(snapshot.get('paper_starting_balance', account.starting_balance) or account.starting_balance)
    account.cash_balance = float(snapshot.get('available_balance', snapshot.get('paper_balance', account.cash_balance)) or 0.0)
    account.equity = float(snapshot.get('paper_equity', account.equity) or 0.0)
    account.realized_pnl = float(snapshot.get('realized_pnl', account.realized_pnl) or 0.0)
    account.unrealized_pnl = float(snapshot.get('unrealized_pnl', account.unrealized_pnl) or 0.0)
    account.margin_reserved = float(snapshot.get('margin_reserved', account.margin_reserved) or 0.0)
    account.open_notional = float(snapshot.get('open_notional', account.open_notional) or 0.0)
    account.updated_at = now

    positions = _normalize_worker_positions(snapshot)
    await db.execute(
        delete(UserPaperPosition).where(UserPaperPosition.user_id == user.id, UserPaperPosition.status == 'OPEN')
    )
    for raw_position in positions:
        symbol = str(raw_position.get('symbol', '')).upper()
        side = str(raw_position.get('side', '')).upper()
        if not symbol or side not in {'LONG', 'SHORT'}:
            continue
        opened_at_raw = raw_position.get('opened_at')
        try:
            opened_at = datetime.fromisoformat(str(opened_at_raw).replace('Z', '+00:00')).replace(tzinfo=None)
        except (TypeError, ValueError):
            opened_at = now
        position = UserPaperPosition(
            user_id=user.id,
            symbol=symbol,
            side=side,
            timeframe=str(raw_position.get('entry_timeframe', '1H')).upper(),
            entry_price=float(raw_position.get('entry_price', 0.0) or 0.0),
            mark_price=float(raw_position.get('mark_price', raw_position.get('entry_price', 0.0)) or 0.0),
            size=float(raw_position.get('position_size', 0.0) or 0.0),
            notional=float(raw_position.get('position_usd', 0.0) or 0.0),
            margin_reserved=float(raw_position.get('margin_reserved', 0.0) or 0.0),
            stop_loss=float(raw_position['stop_loss']) if raw_position.get('stop_loss') is not None else None,
            take_profit=float(raw_position['take_profit']) if raw_position.get('take_profit') is not None else None,
            leverage=float(raw_position.get('leverage', 1.0) or 1.0),
            status='OPEN',
            opened_at=opened_at,
            realized_pnl=0.0,
            created_at=now,
            updated_at=now,
        )
        db.add(position)

    await log_user_event(
        user=user,
        db=db,
        event_type=decision_type,
        severity='success' if positions else 'info',
        message=reason[:240],
        detail=explanation[:1200],
        payload={
            'source': 'global_worker',
            'open_positions': len(positions),
            'paper_equity': account.equity,
            'available_balance': account.cash_balance,
        },
    )
