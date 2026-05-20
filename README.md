# BTC Bot Seguro Avanzado

Bot de trading algorítmico para BTC con arquitectura multi-timeframe, gestión de riesgo y IA asistida.

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
- Protección contra SHORT real accidental en Coinbase spot
- Backend opcional: si `BACKEND_API_URL` está vacío, el bot no intenta postear

## Requisitos

- Python 3.11+ recomendado
- Variables de entorno:
  - `TELEGRAM_TOKEN`
  - `CHAT_ID`
  - `CB_API_KEY`
  - `CB_API_SECRET`
  - `PRODUCT_ID` (por defecto `BTC-USDC`)
  - `DRY_RUN` (`true` o `false`)
  - `USE_AI_ASSIST` (`true` o `false`)
  - `BACKEND_API_URL` (opcional, por ejemplo `https://<backend>/api`)
  - `RUN_ONCE` (`true` para smoke tests)
  - `ALLOW_REAL_SPOT_SHORT` (mantener `false` en Coinbase spot)

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python3 btc_bot.py
```

El bot valida la configuración y ejecuta el loop principal usando Telegram para alertas. En modo `DRY_RUN=true` solo simula órdenes. En modo real, las señales `SHORT` se bloquean por defecto porque Coinbase spot no abre posiciones cortas reales.

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
