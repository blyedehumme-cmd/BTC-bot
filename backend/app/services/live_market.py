from datetime import datetime
import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.models import MarketSnapshot, Signal

COINBASE_API_URL = 'https://api.exchange.coinbase.com'
BINANCE_API_URL = 'https://api.binance.com'
KRAKEN_API_URL = 'https://api.kraken.com'
TIMEOUT = 5


def _coinbase_live_price() -> dict[str, object]:
    ticker = requests.get(f'{COINBASE_API_URL}/products/BTC-USD/ticker', timeout=TIMEOUT)
    ticker.raise_for_status()
    candle_resp = requests.get(
        f'{COINBASE_API_URL}/products/BTC-USD/candles?granularity=3600&limit=2',
        timeout=TIMEOUT,
    )
    candle_resp.raise_for_status()
    ticker_data = ticker.json()
    candle_data = candle_resp.json()
    price = float(ticker_data.get('price', 0))
    change_pct = 0.0
    if isinstance(candle_data, list) and len(candle_data) >= 2:
        previous_close = float(candle_data[0][4])
        if previous_close:
            change_pct = (price - previous_close) / previous_close * 100
    return {
        'symbol': 'BTC-USD',
        'price': price,
        'change_1h_pct': round(change_pct, 2),
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def _binance_live_price() -> dict[str, object]:
    price_resp = requests.get(f'{BINANCE_API_URL}/api/v3/ticker/price?symbol=BTCUSDT', timeout=TIMEOUT)
    price_resp.raise_for_status()
    candle_resp = requests.get(
        f'{BINANCE_API_URL}/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=2',
        timeout=TIMEOUT,
    )
    candle_resp.raise_for_status()
    price_data = price_resp.json()
    candle_data = candle_resp.json()
    price = float(price_data.get('price', 0))
    change_pct = 0.0
    if isinstance(candle_data, list) and len(candle_data) >= 2:
        previous_close = float(candle_data[0][4])
        if previous_close:
            change_pct = (price - previous_close) / previous_close * 100
    return {
        'symbol': 'BTC-USDT',
        'price': price,
        'change_1h_pct': round(change_pct, 2),
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def _kraken_live_price() -> dict[str, object]:
    response = requests.get(f'{KRAKEN_API_URL}/0/public/Ticker?pair=XBTUSD', timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    pair_data = next(iter(data.get('result', {}).values()), {})
    price = float(pair_data.get('c', [0])[0])
    last_trade = float(pair_data.get('p', [0])[0]) if pair_data.get('p') else price
    change_pct = 0.0
    if last_trade:
        change_pct = (price - last_trade) / last_trade * 100
    return {
        'symbol': 'XBT-USD',
        'price': price,
        'change_1h_pct': round(change_pct, 2),
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def fetch_live_market_data() -> dict[str, object]:
    providers = [_coinbase_live_price, _binance_live_price, _kraken_live_price]
    last_exception = None
    for provider in providers:
        try:
            return provider()
        except Exception as exc:
            last_exception = exc
    raise RuntimeError(f'No live market provider available: {last_exception}')


async def get_live_market_status(db: AsyncSession) -> dict[str, object]:
    try:
        market_data = fetch_live_market_data()
        backend_connected = True
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Market data providers unavailable') from exc

    latest_snapshot = await db.scalar(select(MarketSnapshot).order_by(MarketSnapshot.updated_at.desc()).limit(1))
    latest_signal = await db.scalar(select(Signal).order_by(Signal.created_at.desc()).limit(1))
    signal_text = 'WAIT'
    confidence_level = 0
    if latest_signal:
        signal_text = latest_signal.direction
        confidence_level = latest_signal.confidence_score

    support = float(latest_snapshot.support) if latest_snapshot else 0.0
    resistance = float(latest_snapshot.resistance) if latest_snapshot else 0.0
    trend = latest_snapshot.trend if latest_snapshot else 'Unknown'

    return {
        'symbol': market_data['symbol'],
        'price': market_data['price'],
        'change_1h_pct': market_data['change_1h_pct'],
        'signal': signal_text,
        'confidence': confidence_level,
        'support': support,
        'resistance': resistance,
        'trend': trend,
        'updated_at': market_data['updated_at'],
        'backend_connected': backend_connected,
    }
