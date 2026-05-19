from datetime import datetime

from app.services.live_market import fetch_live_market_data


def _support_resistance_from_price(price: float) -> tuple[float, float]:
    return price * 0.995, price * 1.005


def get_market_snapshots() -> list[dict[str, object]]:
    live_data = fetch_live_market_data()
    price = float(live_data.get('price', 0.0))
    support = float(live_data.get('support', price * 0.995))
    resistance = float(live_data.get('resistance', price * 1.005))

    return [
        {
            'symbol': 'BTC/USDT',
            'timeframe': '1H',
            'price': round(price, 2),
            'trend': 'Bullish',
            'support': round(support, 2),
            'resistance': round(resistance, 2),
            'volume': 4820,
            'updated_at': datetime.utcnow().isoformat() + 'Z',
        }
    ]
