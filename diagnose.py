import os
import importlib
import sys

# Configurar entorno para importación segura
os.environ.setdefault('DRY_RUN', 'true')
os.environ.setdefault('CB_API_KEY', 'dummy')
os.environ.setdefault('CB_API_SECRET', 'dummy')
os.environ.setdefault('TELEGRAM_TOKEN', '')
os.environ.setdefault('CHAT_ID', '')

# Asegurar que el path actual está en sys.path
sys.path.insert(0, '.')

btc = importlib.import_module('btc_bot')

# Generar velas de prueba
def make_candles(n, start_price=50000.0):
    candles = []
    for i in range(n):
        price = start_price + (i - n/2) * 1.0
        candles.append({
            'start': i,
            'low': price - 50,
            'high': price + 50,
            'open': price - 5,
            'close': price,
            'volume': 1000 + i,
        })
    return candles

candles_1h = make_candles(180)
candles_4h = make_candles(180)
candles_1d = make_candles(180)
candles_1w = make_candles(80, start_price=49500.0)

print('Ejecutando diagnóstico interno con velas simuladas...')
weekly = btc.timeframe_analysis(candles_1w, '1W')
daily = btc.timeframe_analysis(candles_1d, '1D')
fourh = btc.timeframe_analysis(candles_4h, '4H')
hourly = btc.timeframe_analysis(candles_1h, '1H')
print('Weekly:', weekly)
print('Daily:', daily)
print('4H:', fourh)
print('1H:', hourly)

signal = btc.build_signal(weekly, daily, fourh, hourly)
print('Señal construida:', signal)

balance = btc.get_usdc_balance()
print('Balance USDC (DRY_RUN):', balance)
size = btc.calculate_position_size(balance, hourly['price'], signal.get('atr', 0.0))
print('Tamaño posición (BTC):', size)
print('Tamaño posición (USD):', size * hourly['price'] if hourly['price'] else 0.0)
print('Diagnóstico completado.')
