import pytest


@pytest.mark.asyncio
async def test_health_returns_paper_mode(client):
    response = await client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'paper_trading'
    assert payload['status'] == 'ok'
