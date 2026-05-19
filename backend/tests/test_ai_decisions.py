import pytest


@pytest.mark.asyncio
async def test_ai_decision_creates_log_entry(client):
    decision_response = await client.post(
        '/api/ai/decisions',
        json={
            'signal_id': 0,
            'decision_type': 'analysis_wait',
            'reason': 'Test decision',
            'explanation': 'Unit test explanation',
        },
    )
    assert decision_response.status_code == 200

    logs_response = await client.get('/api/logs')
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) >= 1
    assert logs[0]['message'] == 'Test decision'
