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

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python3 btc_bot.py
```

El bot valida la configuración y ejecuta el loop principal usando Telegram para alertas. En modo `DRY_RUN=true` solo simula órdenes.

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
