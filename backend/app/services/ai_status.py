from datetime import datetime


def get_ai_status() -> dict[str, object]:
    return {
        'engine': 'Online',
        'paper_mode': True,
        'last_decision': 'Approved for paper LONG signal',
        'approved_signals': 7,
        'rejected_signals': 2,
        'risk_level': 'Low',
        'explanation': 'Trend, volume and momentum aligned across 1H and 4H.',
        'last_updated': datetime.utcnow().isoformat() + 'Z',
    }
