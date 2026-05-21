from __future__ import annotations

from datetime import datetime, timedelta
import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.models import MarketSnapshot, Signal

COINBASE_API_URL = 'https://api.exchange.coinbase.com'
BINANCE_API_URL = 'https://api.binance.com'
KRAKEN_API_URL = 'https://api.kraken.com'
TIMEOUT = 5
DEFAULT_CANDLE_LIMIT = 120

TIMEFRAME_SECONDS = {
    '5M': 300,
    '15M': 900,
    '1H': 3600,
    '4H': 14400,
    '1D': 86400,
}

KRAKEN_INTERVALS = {
    '5M': 5,
    '15M': 15,
    '1H': 60,
    '4H': 240,
    '1D': 1440,
}

BINANCE_INTERVALS = {
    '5M': '5m',
    '15M': '15m',
    '1H': '1h',
    '4H': '4h',
    '1D': '1d',
}


def _normalize_timeframe(timeframe: str | None) -> str:
    normalized = (timeframe or '1H').strip().upper()
    return normalized if normalized in TIMEFRAME_SECONDS else '1H'


def _iso_from_timestamp(value: object) -> str:
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
    except (TypeError, ValueError, OSError):
        return datetime.utcnow().isoformat() + 'Z'


def _sort_candles(candles: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    return sorted(candles, key=lambda item: str(item.get('time', '')))


def _normalize_closes(candle_data: list[object], index: int) -> list[float]:
    closes: list[float] = []
    for candle in candle_data:
        if isinstance(candle, list) and len(candle) > index:
            try:
                closes.append(float(candle[index]))
            except (TypeError, ValueError):
                continue
    return closes


def _support_resistance_from_closes(closes: list[float], price: float) -> tuple[float, float]:
    if closes:
        lowest = min(closes)
        highest = max(closes)
        support = min(lowest, price * 0.995)
        resistance = max(highest, price * 1.005)
        return round(support, 2), round(resistance, 2)
    return round(price * 0.995, 2), round(price * 1.005, 2)


def _true_ranges(candles: list[dict[str, float | str]]) -> list[float]:
    ranges: list[float] = []
    for index in range(1, len(candles)):
        high = float(candles[index].get('high', 0) or 0)
        low = float(candles[index].get('low', 0) or 0)
        prev_close = float(candles[index - 1].get('close', 0) or 0)
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return ranges


def _atr(candles: list[dict[str, float | str]], period: int = 14) -> float:
    ranges = _true_ranges(candles)
    if len(ranges) < period:
        return 0.0
    return sum(ranges[-period:]) / period


def _wilder(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    smoothed = [sum(values[:period]) / period]
    for value in values[period:]:
        smoothed.append(((smoothed[-1] * (period - 1)) + value) / period)
    return smoothed


def _adx(candles: list[dict[str, float | str]], period: int = 14) -> float:
    if len(candles) < period * 2 + 1:
        return 0.0

    true_ranges: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []

    for index in range(1, len(candles)):
        high = float(candles[index].get('high', 0) or 0)
        low = float(candles[index].get('low', 0) or 0)
        prev_high = float(candles[index - 1].get('high', 0) or 0)
        prev_low = float(candles[index - 1].get('low', 0) or 0)
        prev_close = float(candles[index - 1].get('close', 0) or 0)

        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    atr_values = _wilder(true_ranges, period)
    plus_values = _wilder(plus_dm, period)
    minus_values = _wilder(minus_dm, period)
    length = min(len(atr_values), len(plus_values), len(minus_values))
    if length == 0:
        return 0.0

    dx_values: list[float] = []
    for index in range(length):
        atr_value = atr_values[index]
        if atr_value <= 0:
            continue
        plus_di = 100 * (plus_values[index] / atr_value)
        minus_di = 100 * (minus_values[index] / atr_value)
        denominator = plus_di + minus_di
        if denominator:
            dx_values.append(100 * abs(plus_di - minus_di) / denominator)

    adx_values = _wilder(dx_values, period)
    return adx_values[-1] if adx_values else 0.0


def _volume_ratio(candles: list[dict[str, float | str]], period: int = 20) -> float:
    volumes = [float(candle.get('volume', 0) or 0) for candle in candles]
    if len(volumes) < period + 1:
        return 1.0
    average = sum(volumes[-period - 1:-1]) / period
    return volumes[-1] / average if average else 1.0


def _indicators(candles: list[dict[str, float | str]]) -> dict[str, float]:
    latest_volume = float(candles[-1].get('volume', 0) or 0) if candles else 0.0
    return {
        'adx': round(_adx(candles), 2),
        'atr': round(_atr(candles), 2),
        'volume': round(latest_volume, 4),
        'volume_ratio': round(_volume_ratio(candles), 2),
    }


def _coinbase_live_price(timeframe: str) -> dict[str, object]:
    ticker = requests.get(f'{COINBASE_API_URL}/products/BTC-USD/ticker', timeout=TIMEOUT)
    ticker.raise_for_status()
    seconds = TIMEFRAME_SECONDS[timeframe]
    end = datetime.utcnow()
    start = end - timedelta(seconds=seconds * DEFAULT_CANDLE_LIMIT)
    candle_resp = requests.get(
        f'{COINBASE_API_URL}/products/BTC-USD/candles',
        params={
            'granularity': seconds,
            'start': start.isoformat(),
            'end': end.isoformat(),
        },
        timeout=TIMEOUT,
    )
    candle_resp.raise_for_status()
    ticker_data = ticker.json()
    candle_data = candle_resp.json()
    price = float(ticker_data.get('price', 0))
    change_pct = 0.0
    candles = _sort_candles([
        {
            'time': _iso_from_timestamp(row[0]),
            'low': float(row[1]),
            'high': float(row[2]),
            'open': float(row[3]),
            'close': float(row[4]),
            'volume': float(row[5]),
        }
        for row in candle_data
        if isinstance(row, list) and len(row) >= 6
    ])[-DEFAULT_CANDLE_LIMIT:]
    closes = [float(candle['close']) for candle in candles]
    if len(closes) >= 2:
        previous_close = closes[-2]
        if previous_close:
            change_pct = (price - previous_close) / previous_close * 100
    support, resistance = _support_resistance_from_closes(closes, price)
    return {
        'exchange': 'coinbase',
        'symbol': 'BTC-USD',
        'timeframe': timeframe,
        'price': price,
        'change_1h_pct': round(change_pct, 2),
        'support': round(support, 2),
        'resistance': round(resistance, 2),
        'candles': candles,
        **_indicators(candles),
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def _binance_live_price(timeframe: str) -> dict[str, object]:
    price_resp = requests.get(f'{BINANCE_API_URL}/api/v3/ticker/price?symbol=BTCUSDT', timeout=TIMEOUT)
    price_resp.raise_for_status()
    candle_resp = requests.get(
        f'{BINANCE_API_URL}/api/v3/klines?symbol=BTCUSDT&interval={BINANCE_INTERVALS[timeframe]}&limit={DEFAULT_CANDLE_LIMIT}',
        timeout=TIMEOUT,
    )
    candle_resp.raise_for_status()
    price_data = price_resp.json()
    candle_data = candle_resp.json()
    price = float(price_data.get('price', 0))
    change_pct = 0.0
    candles = _sort_candles([
        {
            'time': _iso_from_timestamp(row[0]),
            'open': float(row[1]),
            'high': float(row[2]),
            'low': float(row[3]),
            'close': float(row[4]),
            'volume': float(row[5]),
        }
        for row in candle_data
        if isinstance(row, list) and len(row) >= 6
    ])
    closes = [float(candle['close']) for candle in candles]
    if len(closes) >= 2:
        previous_close = closes[-2]
        if previous_close:
            change_pct = (price - previous_close) / previous_close * 100
    support, resistance = _support_resistance_from_closes(closes, price)
    return {
        'exchange': 'binance',
        'symbol': 'BTC-USDT',
        'timeframe': timeframe,
        'price': price,
        'change_1h_pct': round(change_pct, 2),
        'support': round(support, 2),
        'resistance': round(resistance, 2),
        'candles': candles,
        **_indicators(candles),
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def _kraken_live_price(timeframe: str) -> dict[str, object]:
    response = requests.get(f'{KRAKEN_API_URL}/0/public/Ticker?pair=XBTUSD', timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    pair_data = next(iter(data.get('result', {}).values()), {})
    price = float(pair_data.get('c', [0])[0])
    change_pct = 0.0
    since = int((datetime.utcnow() - timedelta(seconds=TIMEFRAME_SECONDS[timeframe] * DEFAULT_CANDLE_LIMIT)).timestamp())
    ohlc_resp = requests.get(
        f'{KRAKEN_API_URL}/0/public/OHLC?pair=XBTUSD&interval={KRAKEN_INTERVALS[timeframe]}&since={since}',
        timeout=TIMEOUT,
    )
    ohlc_resp.raise_for_status()
    ohlc_data = ohlc_resp.json()
    raw_ohlc = next(iter(ohlc_data.get('result', {}).values()), [])
    candles = _sort_candles([
        {
            'time': _iso_from_timestamp(row[0]),
            'open': float(row[1]),
            'high': float(row[2]),
            'low': float(row[3]),
            'close': float(row[4]),
            'volume': float(row[6]),
        }
        for row in raw_ohlc
        if isinstance(row, list) and len(row) >= 7
    ])[-DEFAULT_CANDLE_LIMIT:]
    closes = [float(candle['close']) for candle in candles]
    if len(closes) >= 2:
        previous_close = closes[-2]
        if previous_close:
            change_pct = (price - previous_close) / previous_close * 100
    support, resistance = _support_resistance_from_closes(closes, price)
    return {
        'exchange': 'kraken',
        'symbol': 'XBT-USD',
        'timeframe': timeframe,
        'price': price,
        'change_1h_pct': round(change_pct, 2),
        'support': round(support, 2),
        'resistance': round(resistance, 2),
        'candles': candles,
        **_indicators(candles),
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def fetch_live_market_data(timeframe: str = '1H') -> dict[str, object]:
    selected_timeframe = _normalize_timeframe(timeframe)
    providers = [_coinbase_live_price, _kraken_live_price, _binance_live_price]
    last_exception = None
    for provider in providers:
        try:
            return provider(selected_timeframe)
        except Exception as exc:
            last_exception = exc
    raise RuntimeError(f'No live market provider available: {last_exception}')


async def get_live_market_status(db: AsyncSession, timeframe: str = '1H') -> dict[str, object]:
    try:
        market_data = fetch_live_market_data(timeframe)
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

    support = float(market_data.get('support', 0.0))
    resistance = float(market_data.get('resistance', 0.0))
    trend = latest_snapshot.trend if latest_snapshot else 'Unknown'

    return {
        'symbol': market_data['symbol'],
        'exchange': market_data.get('exchange'),
        'timeframe': market_data.get('timeframe'),
        'price': market_data['price'],
        'change_1h_pct': market_data['change_1h_pct'],
        'signal': signal_text,
        'confidence': confidence_level,
        'support': support,
        'resistance': resistance,
        'trend': trend,
        'adx': market_data.get('adx'),
        'atr': market_data.get('atr'),
        'volume': market_data.get('volume'),
        'volume_ratio': market_data.get('volume_ratio'),
        'candles': market_data.get('candles', []),
        'updated_at': market_data['updated_at'],
        'backend_connected': backend_connected,
    }
