from typing import Any


def generate_paper_signal(market_snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        'symbol': market_snapshot['symbol'],
        'timeframe': market_snapshot['timeframe'],
        'direction': 'LONG',
        'confidence_score': 80,
        'risk_level': 'Low',
        'market_condition': 'Trending',
        'approved': True,
        'explanation': 'Simulated signal generated for paper trading only.',
    }
