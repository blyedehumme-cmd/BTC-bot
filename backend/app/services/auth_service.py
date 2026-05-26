from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.database import get_db
from app.models.models import User

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if not EMAIL_RE.match(normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Email inválido.')
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='La contraseña debe tener al menos 8 caracteres.',
        )


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 210_000)
    return f'pbkdf2_sha256$210000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}'


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = password_hash.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode('ascii'))


def create_access_token(user: User) -> str:
    now = int(time.time())
    payload = {
        'sub': str(user.id),
        'email': user.email,
        'iat': now,
        'exp': int((datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    header = {'alg': 'HS256', 'typ': 'JWT'}
    signing_input = f'{_b64url_encode(json.dumps(header, separators=(",", ":")).encode())}.{_b64url_encode(json.dumps(payload, separators=(",", ":")).encode())}'
    signature = hmac.new(settings.secret_key.encode('utf-8'), signing_input.encode('ascii'), hashlib.sha256).digest()
    return f'{signing_input}.{_b64url_encode(signature)}'


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split('.', 2)
        signing_input = f'{header_b64}.{payload_b64}'
        expected = hmac.new(settings.secret_key.encode('utf-8'), signing_input.encode('ascii'), hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(actual, expected):
            raise ValueError('bad signature')
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get('exp', 0)) < int(time.time()):
            raise ValueError('expired')
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Sesión inválida o expirada.') from exc


def encryption() -> Fernet:
    key = settings.encryption_key.strip() or settings.secret_key
    digest = hashlib.sha256(key.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return encryption().encrypt(value.encode('utf-8')).decode('utf-8')


def decrypt_secret(value: str) -> str:
    try:
        return encryption().decrypt(value.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail='No se pudo descifrar la credencial.') from exc


def preview_secret(value: str) -> str:
    if len(value) <= 8:
        return '****'
    return f'{value[:4]}...{value[-4:]}'


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token requerido.')
    payload = decode_access_token(authorization.split(' ', 1)[1].strip())
    user_id = int(payload.get('sub', 0))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuario no disponible.')
    return user
