from app.services.live_market import _support_resistance_from_closes


def test_support_resistance_from_closes():
    closes = [100.0, 102.0, 98.0, 101.0]
    support, resistance = _support_resistance_from_closes(closes, price=100.0)
    assert support <= 100.0
    assert resistance >= 100.0
    assert support == 98.0
    assert resistance == 102.0


def test_support_resistance_fallback_without_closes():
    support, resistance = _support_resistance_from_closes([], price=1000.0)
    assert support == 995.0
    assert resistance == 1005.0
