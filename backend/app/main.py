from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import api_router

app = FastAPI(
    title='Lesly AI Trading Backend',
    description='FastAPI scaffold for Lesly AI Trading — paper trading mode only.',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(api_router, prefix='/api')


@app.on_event('startup')
async def on_startup():
    from app.services.db_init import init_db

    await init_db()


@app.get('/')
async def root():
    return {
        'status': 'ok',
        'message': 'Lesly backend scaffold is ready. No real trading executed.',
    }
