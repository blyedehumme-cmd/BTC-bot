from datetime import datetime


def get_market_snapshots() -> list[dict[str, object]]:
    return [
        {
            'symbol': 'BTC/USDT',
            'timeframe': '1H',
            'price': 63498,
            'trend': 'Bullish',
            'support': 63120,
            'resistance': 63860,
            'volume': 4820,
            'updated_at': datetime.utcnow().isoformat() + 'Z',
        }
    ]
