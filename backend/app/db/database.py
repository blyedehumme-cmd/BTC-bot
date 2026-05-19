import ssl
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings


def _connect_args() -> dict:
    if not settings.database_ssl:
        return {}
    return {'ssl': ssl.create_default_context()}


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args(),
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
