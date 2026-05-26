import pytest
import json
from uuid import uuid4


@pytest.mark.asyncio
async def test_register_login_and_exchange_account(client):
    email = f'lesly-{uuid4().hex[:8]}@example.com'
    register = await client.post('/api/auth/register', json={
        'email': email,
        'name': 'Lesly',
        'password': 'super-secret-123',
    })
    assert register.status_code == 200
    token = register.json()['access_token']

    me = await client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['email'] == email

    account = await client.post(
        '/api/auth/exchange-accounts',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'exchange': 'kraken',
            'api_key': 'KRAKEN123456789',
            'api_secret': 'SECRET123',
            'passphrase': 'optional',
            'dry_run': True,
        },
    )
    assert account.status_code == 200
    payload = account.json()
    assert payload['exchange'] == 'kraken'
    assert payload['dry_run'] is True
    assert payload['api_key_preview'] == 'KRAK...6789'
    assert payload['has_secret'] is True

    accounts = await client.get('/api/auth/exchange-accounts', headers={'Authorization': f'Bearer {token}'})
    assert accounts.status_code == 200
    assert len(accounts.json()) == 1

    okx_account = await client.post(
        '/api/auth/exchange-accounts',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'exchange': 'okx',
            'api_key': 'OKX123456789',
            'api_secret': 'SECRET123',
            'passphrase': 'required-on-okx',
            'dry_run': True,
        },
    )
    assert okx_account.status_code == 200
    assert okx_account.json()['exchange'] == 'okx'

    binance_account = await client.post(
        '/api/auth/exchange-accounts',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'exchange': 'binance',
            'api_key': 'BINANCE123456789',
            'api_secret': 'SECRET123',
            'dry_run': True,
        },
    )
    assert binance_account.status_code == 200
    assert binance_account.json()['exchange'] == 'binance'

    settings = await client.get('/api/auth/bot-settings', headers={'Authorization': f'Bearer {token}'})
    assert settings.status_code == 200
    assert settings.json()['paper_balance'] == 5000.0
    assert settings.json()['symbols'] == 'BTC,ETH'

    updated_settings = await client.put(
        '/api/auth/bot-settings',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'active': True,
            'selected_exchange': 'okx',
            'symbols': 'BTC',
            'paper_balance': 7500,
            'max_open_positions': 1,
            'risk_profile': 'conservative',
        },
    )
    assert updated_settings.status_code == 200
    updated_payload = updated_settings.json()
    assert updated_payload['active'] is True
    assert updated_payload['selected_exchange'] == 'okx'
    assert updated_payload['symbols'] == 'BTC'
    assert updated_payload['paper_balance'] == 7500
    assert updated_payload['max_open_positions'] == 1

    runtime = await client.get('/api/auth/paper-runtime', headers={'Authorization': f'Bearer {token}'})
    assert runtime.status_code == 200
    runtime_payload = runtime.json()
    assert runtime_payload['account']['starting_balance'] == 7500.0
    assert runtime_payload['account']['equity'] == 7500.0
    assert runtime_payload['active_exchange'] == 'okx'
    assert runtime_payload['active_symbols'] == ['BTC']
    assert runtime_payload['exchange_ready'] is True
    assert runtime_payload['open_positions_count'] == 0

    reset_runtime = await client.post('/api/auth/paper-runtime/reset', headers={'Authorization': f'Bearer {token}'})
    assert reset_runtime.status_code == 200
    reset_payload = reset_runtime.json()
    assert reset_payload['account']['cash_balance'] == 7500.0
    assert reset_payload['latest_events'][0]['event_type'] == 'paper_runtime_reset'

    worker_status = await client.post(
        '/api/ai/decisions',
        json={
            'signal_id': 0,
            'decision_type': 'position_status',
            'reason': 'Worker status: 1 open.',
            'condition_snapshot': json.dumps({
                'paper_starting_balance': 7500.0,
                'paper_balance': 7600.0,
                'available_balance': 5100.0,
                'margin_reserved': 2500.0,
                'open_notional': 7500.0,
                'unrealized_pnl': 100.0,
                'paper_equity': 7700.0,
                'realized_pnl': 100.0,
                'open_positions': [{
                    'status': 'OPEN',
                    'symbol': 'BTC',
                    'entry_timeframe': '1D',
                    'side': 'LONG',
                    'entry_price': 76000.0,
                    'mark_price': 77000.0,
                    'position_size': 0.1,
                    'position_usd': 7500.0,
                    'margin_reserved': 2500.0,
                    'stop_loss': 74500.0,
                    'take_profit': 80000.0,
                    'leverage': 3.0,
                    'opened_at': '2026-05-25T04:00:00Z',
                }],
            }),
            'explanation': 'Estado actual de posiciones paper publicado por el worker.',
        },
    )
    assert worker_status.status_code == 200
    synced_runtime = await client.get('/api/auth/paper-runtime', headers={'Authorization': f'Bearer {token}'})
    assert synced_runtime.status_code == 200
    synced_payload = synced_runtime.json()
    assert synced_payload['account']['equity'] == 7700.0
    assert synced_payload['open_positions_count'] == 1
    assert synced_payload['open_positions'][0]['symbol'] == 'BTC'
    assert synced_payload['open_positions'][0]['leverage'] == 3.0

    login = await client.post('/api/auth/login', json={
        'email': email,
        'password': 'super-secret-123',
    })
    assert login.status_code == 200
    assert login.json()['user']['email'] == email
