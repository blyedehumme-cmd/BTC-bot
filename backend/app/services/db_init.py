import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.settings import settings
from app.db.database import engine
from app.models.models import Base

logger = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def run_alembic_migrations() -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / 'alembic.ini'))
    alembic_cfg.set_main_option('sqlalchemy.url', settings.database_url)
    command.upgrade(alembic_cfg, 'head')
    logger.info('Alembic migrations applied.')


async def init_db() -> None:
    if settings.use_alembic_only:
        await asyncio.to_thread(run_alembic_migrations)
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
