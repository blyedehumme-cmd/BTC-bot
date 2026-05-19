# Backend Architecture for Lesly AI Trading

## Propósito

Este backend es un scaffold inicial para el motor de señales y la API de Lesly. Se diseña para:

- Mantener `paper trading` como modo por defecto.
- No ejecutar órdenes reales.
- No conectar Coinbase todavía.
- Ser escalable con FastAPI y PostgreSQL.

## Componentes principales

### Frontend

- `lesly-frontend/`
- Next.js + React + Tailwind CSS

### Backend

- `backend/app/main.py` — aplicación FastAPI principal
- `backend/app/api/` — endpoints REST para salud y señales
- `backend/app/core/` — configuración y settings
- `backend/app/db/` — conexión y sesión de la base de datos
- `backend/app/models/` — modelos SQLAlchemy
- `backend/app/schemas/` — DTOs Pydantic
- `backend/app/services/` — lógica de señal, datos de mercado y aprendizaje futuro
- `backend/app/utils/` — utilidades comunes (logger, seguridad)

## Flujo inicial

1. `GET /api/health` devuelve estado de salud y modo `paper_trading`.
2. `GET /api/signals` devuelve señales simuladas.
3. `POST /api/signals` crea una señal de ejemplo con explicación.
4. El backend registra y prepara datos para futuros módulos de aprendizaje.

## Base de datos futura

Tablas iniciales:

- `signals`
- `trades_paper`
- `ai_decisions`
- `market_snapshots`
- `strategy_performance`
- `rejected_signals`
- `learning_notes`

## Siguiente paso recomendado

1. Implementar migraciones con Alembic.
2. Agregar conexión a PostgreSQL.
3. Construir `signal_engine` y `risk_engine` con reglas de paper trading.
4. Diseñar `ai_learning` para registrar resultados y evaluar performance.
5. Conectar el frontend al backend con fetch/axios.
