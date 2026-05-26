# BTC Bot Seguro Avanzado

Bot de trading algorítmico para BTC con arquitectura multi-timeframe, gestión de riesgo y IA asistida.

## Perfil activo: BTC + ETH

La configuración de producción actual queda limitada a BTC y ETH. BTC usa el perfil `btc_swing_v1`; ETH queda separado con reglas más restrictivas, operando solo señales SHORT en el perfil validado para ese activo.

Resultado de referencia del backtest BTC swing validado:

- Capital inicial: `$5,000.00`
- Capital final: `$17,051.51`
- Retorno total: `+241.03%`
- Max drawdown: `-14.60%`
- Win rate: `48.85%`
- Trailing stop: `2.0 ATR` simple

Por esa razón, el `WATCHLIST` de Render queda en `BTC,ETH`. Las demás criptomonedas no forman parte del frontend ni del backend activo.

El paper trading usa una sola cuenta simulada de `$5,000`. Si BTC y ETH tienen operaciones abiertas al mismo tiempo, ambas comparten ese mismo capital: el margen reservado se descuenta del disponible y el frontend muestra equity, margen, contrato abierto y PnL flotante consolidados.

El contexto HMM de produccion queda en `hmm_context.json` con BTC y ETH. En Render se usa `HMM_REGIME_CONTEXT_FILE=hmm_context.json`; el filtro automatico HMM sigue desactivado por defecto, asi que HMM aporta contexto al Supervisor/IA sin bloquear operaciones por si solo.

## Características principales

- Multi-timeframe: 1W, 1D, 4H, 1H
- Reglas de tendencia LONG / SHORT
- Gestión de riesgo con límite diario y máximo trades por día
- Trailing stop dinámico
- IA asistida como filtro de calidad (no controla la estrategia)
- Notificaciones por Telegram
- Modo `DRY_RUN` para simulación
- ATR real basado en high/low/close
- ADX suavizado estilo Wilder
- Soporte configurable para Coinbase Advanced Trade, Kraken Pro Spot y simulacion Kraken Futures
- Protección contra SHORT real accidental en exchanges spot
- Backend opcional: si `BACKEND_API_URL` está vacío, el bot no intenta postear

## Requisitos

- Python 3.11+ recomendado
- Variables de entorno:
  - `TELEGRAM_TOKEN`
  - `CHAT_ID`
  - `CB_API_KEY`
  - `CB_API_SECRET`
  - `EXCHANGE` (`coinbase` o `kraken`, por defecto `kraken`)
  - `EXCHANGE_MODE` (`spot` o `futures`, por defecto `futures` con `DRY_RUN=true`)
  - `PRODUCT_ID` (por defecto `BTC-USDC`)
  - `KRAKEN_API_KEY`
  - `KRAKEN_API_SECRET`
  - `KRAKEN_PAIR` (por defecto `XBTUSD`)
  - `KRAKEN_FUTURES_SYMBOL` (por defecto `PI_XBTUSD`)
  - `KRAKEN_QUOTE_ASSET` (por defecto `ZUSD`)
  - `MAX_LEVERAGE` (capado internamente a `3x`)
  - `STRATEGY_PROFILE` (`btc_swing_v1` para la estrategia BTC actual)
  - `OPTIMIZED_SYMBOLS` (`BTC,ETH`)
  - `WATCHLIST` (`BTC,ETH`)
  - `SYMBOL_SIGNAL_SIDES` (`BTC:LONG,SHORT;ETH:SHORT`)
  - `SYMBOL_HMM_REGIMES` (`ETH:4`)
  - `DRY_RUN` (`true` o `false`)
  - `USE_AI_ASSIST` (`true` o `false`)
  - `BACKEND_API_URL` (opcional, por ejemplo `https://<backend>/api`)
  - `RUN_ONCE` (`true` para smoke tests)
  - `ALLOW_REAL_SPOT_SHORT` (mantener `false` en Coinbase spot)
  - `TELEGRAM_POLLING_ENABLED` (`false` recomendado en Render para evitar conflictos `getUpdates`)

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python3 btc_bot.py
```

El bot valida la configuración y ejecuta el loop principal. En modo `DRY_RUN=true` solo simula órdenes. En modo real, las señales `SHORT` se bloquean por defecto porque spot no abre posiciones cortas reales sin margin/futures.

### Usar Kraken Pro / Futures en simulación

Para usar Kraken en vez de Coinbase en modo paper/futures:

```bash
EXCHANGE=kraken
EXCHANGE_MODE=futures
MAX_LEVERAGE=3
KRAKEN_API_KEY=...
KRAKEN_API_SECRET=...
KRAKEN_PAIR=XBTUSD
KRAKEN_FUTURES_SYMBOL=PI_XBTUSD
KRAKEN_QUOTE_ASSET=ZUSD
DRY_RUN=true
```

En `DRY_RUN=true`, el bot simula LONG/SHORT tipo futures con apalancamiento maximo 3x. Si `EXCHANGE_MODE=spot`, las órdenes market reales de Kraken usan `volume` del activo base. El modo real de Kraken Futures queda bloqueado hasta implementar y probar la API privada de futures, para evitar que una señal se ejecute en el mercado equivocado.

Telegram puede enviar notificaciones sin polling. Para evitar `telegram.error.Conflict: terminated by other getUpdates request` en Render, deja:

```bash
TELEGRAM_POLLING_ENABLED=false
```

Activa `TELEGRAM_POLLING_ENABLED=true` solo si quieres comandos `/start`, `/pause`, `/status`, etc. y tienes una sola instancia del bot usando ese token.

## Comandos de Telegram

- `/start` - Activar el bot
- `/pause` - Pausar nuevas operaciones
- `/status` - Ver estado actual
- `/config` - Ver configuración activa
- `/stats` - Ver estadísticas
- `/signal` - Ver última señal generada

## Diagnóstico rápido

Para validar la lógica interna sin depender de Coinbase, usa:

```bash
python3 diagnose.py
```

## Evolución prevista

1. Soporte LONG y SHORT completo
2. Filtro de IA más avanzado
3. Backtesting profesional
4. Paper trading y producción gradual
5. Escalabilidad multiusuario

## Lesly Dashboard (frontend + backend)

| Carpeta | Rol |
|---------|-----|
| `lesly-frontend/` | Dashboard Next.js (paper trading UI) |
| `backend/` | API FastAPI + base de datos |

El bot envía señales al backend con `BACKEND_API_URL`. El dashboard lee datos en vivo desde la API.

### Despliegue

Guía completa: [DEPLOYMENT.md](DEPLOYMENT.md)

Resumen:

1. Backend en Railway/Render + PostgreSQL (`DATABASE_URL`)
2. Frontend en Vercel con `NEXT_PUBLIC_BACKEND_URL=https://<backend>/api`
3. Bot en tu máquina/VPS con el mismo `BACKEND_API_URL`

### Variables del bot para el backend

```bash
BACKEND_API_URL=http://localhost:8000/api   # local
# BACKEND_API_URL=https://your-backend.railway.app/api   # producción
```

### Smoke test del bot

```bash
DRY_RUN=true USE_AI_ASSIST=false RUN_ONCE=true MIN_CONFIDENCE=1.1 python3 btc_bot.py
```
