from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def health_check():
    return {
        'status': 'healthy',
        'mode': 'paper_trading',
        'message': 'Backend is running in paper trading mode only.',
    }
