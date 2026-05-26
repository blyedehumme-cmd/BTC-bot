import pytest
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

    login = await client.post('/api/auth/login', json={
        'email': email,
        'password': 'super-secret-123',
    })
    assert login.status_code == 200
    assert login.json()['user']['email'] == email
