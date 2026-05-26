from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.models import User, UserExchangeAccount
from app.schemas.schemas import (
    AuthTokenResponse,
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    create_access_token,
    decrypt_secret,
    encrypt_secret,
    get_current_user,
    hash_password,
    normalize_email,
    preview_secret,
    validate_email,
    validate_password,
    verify_password,
)

router = APIRouter()

SUPPORTED_USER_EXCHANGES = {'kraken', 'coinbase', 'binance', 'okx'}


def user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def exchange_response(account: UserExchangeAccount) -> ExchangeAccountResponse:
    api_key_preview = preview_secret(decrypt_secret(account.api_key_encrypted))
    return ExchangeAccountResponse(
        id=account.id,
        exchange=account.exchange,
        account_label=account.account_label,
        permissions=account.permissions,
        dry_run=account.dry_run,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
        api_key_preview=api_key_preview,
        has_secret=bool(account.api_secret_encrypted),
        has_passphrase=bool(account.passphrase_encrypted),
    )


@router.post('/register', response_model=AuthTokenResponse)
async def register(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    email = validate_email(payload.email)
    validate_password(payload.password)
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Nombre inválido.')

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Ese email ya está registrado.')

    now = datetime.utcnow()
    user = User(
        email=email,
        name=name,
        password_hash=hash_password(payload.password),
        is_active=True,
        paper_trading=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AuthTokenResponse(access_token=create_access_token(user), user=user_response(user))


@router.post('/login', response_model=AuthTokenResponse)
async def login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    email = normalize_email(payload.email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Email o contraseña incorrectos.')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Usuario desactivado.')
    return AuthTokenResponse(access_token=create_access_token(user), user=user_response(user))


@router.get('/me', response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return user_response(current_user)


@router.get('/exchange-accounts', response_model=list[ExchangeAccountResponse])
async def list_exchange_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserExchangeAccount)
        .where(UserExchangeAccount.user_id == current_user.id)
        .order_by(UserExchangeAccount.created_at.desc())
    )
    return [exchange_response(account) for account in result.scalars().all()]


@router.post('/exchange-accounts', response_model=ExchangeAccountResponse)
async def upsert_exchange_account(
    payload: ExchangeAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exchange = payload.exchange.strip().lower()
    if exchange not in SUPPORTED_USER_EXCHANGES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Exchange no soportado.')
    label = payload.account_label.strip().lower() or 'main'
    now = datetime.utcnow()
    existing = await db.execute(
        select(UserExchangeAccount).where(
            UserExchangeAccount.user_id == current_user.id,
            UserExchangeAccount.exchange == exchange,
            UserExchangeAccount.account_label == label,
        )
    )
    account = existing.scalar_one_or_none()
    if account is None:
        account = UserExchangeAccount(
            user_id=current_user.id,
            exchange=exchange,
            account_label=label,
            api_key_encrypted=encrypt_secret(payload.api_key.strip()),
            api_secret_encrypted=encrypt_secret(payload.api_secret.strip()),
            passphrase_encrypted=encrypt_secret(payload.passphrase.strip()) if payload.passphrase else None,
            permissions='trade_only',
            dry_run=True if payload.dry_run is None else payload.dry_run,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(account)
    else:
        account.api_key_encrypted = encrypt_secret(payload.api_key.strip())
        account.api_secret_encrypted = encrypt_secret(payload.api_secret.strip())
        account.passphrase_encrypted = encrypt_secret(payload.passphrase.strip()) if payload.passphrase else None
        account.dry_run = True if payload.dry_run is None else payload.dry_run
        account.is_active = True
        account.updated_at = now
    await db.commit()
    await db.refresh(account)
    return exchange_response(account)
