import pytest


@pytest.mark.asyncio
async def test_bot_start_stop_status(client):
    stop_response = await client.post('/api/bot/stop')
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped['active'] is False
    assert stopped['mode'] == 'DRY_RUN'

    status_response = await client.get('/api/bot/status')
    assert status_response.status_code == 200
    assert status_response.json()['active'] is False

    start_response = await client.post('/api/bot/start')
    assert start_response.status_code == 200
    started = start_response.json()
    assert started['active'] is True
    assert started['mode'] == 'DRY_RUN'
