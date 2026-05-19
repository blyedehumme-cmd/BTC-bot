# Lesly Backend (FastAPI)\n\nEstructura inicial para el backend de Lesly AI Trading.\n\n## Objetivo\n\nEsta carpeta contiene el scaffold de un backend en Python FastAPI diseñado para paper trading, análisis de señales y almacenamiento en PostgreSQL. Actualmente no ejecuta operaciones reales ni se conecta a Coinbase.\n\n## Ejecutar local\n\n1. Crear un entorno virtual:\n\n```bash\ncd backend\npython3 -m venv .venv\nsource .venv/bin/activate\n```

2. Instalar dependencias:

```bash
python3 -m pip install -r requirements.txt
```

3. Correr el servidor de desarrollo:

```bash
uvicorn app.main:app --reload --port 8000
```

## Migraciones Alembic

1. Generar migración inicial:

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
```

2. Aplicar migración:

```bash
alembic upgrade head
```

Si no quieres usar Alembic todavía, puedes crear tablas directamente con:

```bash
python3 -c "from app.services.db_init import init_db; import asyncio; asyncio.run(init_db())"
```

## Notas importantes

- Modo paper trading solamente.
- No hay lógica de ejecución real.
- No se conecta a Coinbase todavía.

## Endpoints disponibles

- `GET /api/health` — estado de servicio y modo paper trading
- `GET /api/signals` — señales simuladas de paper trading
- `POST /api/signals` — crea una señal simulada con explicación
- `GET /api/logs` — logs de decisiones de IA simulados
- `GET /api/market/snapshots` — snapshots de mercado simulados
- `POST /api/market/snapshots` — guarda un nuevo snapshot de mercado en la base de datos
- `GET /api/ai/status` — estado del motor AI y última decisión
- `GET /api/ai/performance` — resumen de performance simulado
- `POST /api/db/init` — crea las tablas de base de datos desde el modelo SQLAlchemy
