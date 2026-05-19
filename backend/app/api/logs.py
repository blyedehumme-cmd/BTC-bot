from fastapi import APIRouter
from app.schemas.schemas import AiLogResponse

router = APIRouter()


@router.get('/', response_model=list[AiLogResponse])
async def list_logs():
    return [
        {
            'time': '00:02',
            'message': 'AI detected bullish momentum on BTC 1H.',
            'severity': 'info',
            'detail': 'Paper signal evaluated in low volatility conditions.',
        },
        {
            'time': '00:07',
            'message': 'Risk filter approved paper signal with low volatility.',
            'severity': 'success',
            'detail': 'No real order will be executed.',
        },
        {
            'time': '00:15',
            'message': 'No real trade executed — paper mode active.',
            'severity': 'warning',
            'detail': 'Real execution locked until manual activation.',
        },
        {
            'time': '00:23',
            'message': 'Signal confidence 87% after multi-timeframe alignment.',
            'severity': 'info',
            'detail': '1H and 4H momentum aligned for a simulated LONG.',
        },
        {
            'time': '00:31',
            'message': 'AI analyzed support zone and pending liquidity break.',
            'severity': 'info',
            'detail': 'Paper trade signal remains under review.',
        },
    ]
