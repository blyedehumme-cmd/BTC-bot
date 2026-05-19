import pytest


@pytest.mark.asyncio
async def test_performance_shape(client):
    response = await client.get('/api/ai/performance')
    assert response.status_code == 200
    payload = response.json()
    assert 'total_trades' in payload
    assert 'total_signals' in payload
    assert 'wins' in payload
    assert 'losses' in payload
    assert 'win_rate' in payload
