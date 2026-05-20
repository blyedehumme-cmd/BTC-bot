import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.settings import settings
from app.services.db_init import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='Lesly AI Trading Backend',
    description='FastAPI API for Lesly AI Trading — paper trading mode only. Signal logic runs in btc_bot.py.',
    version='0.2.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(api_router, prefix='/api')


@app.on_event('startup')
async def on_startup():
    logger.info('Starting Lesly backend (env=%s)', settings.environment)
    try:
        await asyncio.wait_for(init_db(), timeout=45)
    except Exception:
        logger.exception('Database initialization failed; starting API in degraded mode.')
    logger.info('CORS origins: %s', settings.cors_origin_list)
    if settings.cors_origin_regex:
        logger.info('CORS regex: %s', settings.cors_origin_regex)


@app.get('/')
async def root():
    return {
        'status': 'ok',
        'message': 'Lesly backend is ready. Paper trading only — signals are produced by btc_bot.py.',
        'environment': settings.environment,
        'database': 'postgresql' if settings.database_url.startswith('postgresql') else 'sqlite',
    }
