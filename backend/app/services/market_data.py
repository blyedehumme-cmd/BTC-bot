from __future__ import annotations

from typing import Any


def fetch_market_snapshot(symbol: str, timeframe: str) -> dict[str, Any]:
    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'candles': [],
        'volume': 0,
        'trend': 'unknown',
    }
