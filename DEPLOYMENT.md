# Deployment Guide — Lesly / BTC-bot

## Architecture

- **btc_bot.py** — runs on your machine or a VPS (Render worker, Railway, etc.). Produces signals and POSTs to the backend.
- **backend/** — FastAPI API + database. Deploy to Railway, Render, or Fly.io (not Vercel serverless for long-running DB).
- **lesly-frontend/** — Next.js dashboard. Deploy to Vercel.

```mermaid
flowchart LR
  Bot[btc_bot.py] -->|POST| API[FastAPI]
  UI[Next.js on Vercel] -->|GET| API
  API --> DB[(PostgreSQL)]
```

## 1. Database (PostgreSQL)

Create a free database on [Neon](https://neon.tech), [Supabase](https://supabase.com), or Railway.

Set in the Render backend environment:

```bash
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
ENVIRONMENT=production
SECRET_KEY=<random-long-string>
FRONTEND_URL=https://your-app.vercel.app
CORS_ORIGINS=https://your-app.vercel.app
CORS_ALLOW_VERCEL_PREVIEWS=true
```

The backend normalizes `postgres://` and `postgresql://` URLs to `postgresql+asyncpg://`, enables SSL for Neon, and runs Alembic migrations on startup.

See [RENDER_SETUP.md](RENDER_SETUP.md) for a step-by-step checklist.

## 2. Backend (Railway / Render / Docker)

From `backend/`:

```bash
cp .env.example .env
# edit DATABASE_URL and other vars
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Docker:

```bash
cd backend
docker build -t lesly-backend .
docker run -p 8000:8000 --env-file .env lesly-backend
```

The Dockerfile runs `alembic upgrade head` before starting Uvicorn.

Health check: `GET https://<backend-host>/api/health`

## 3. Frontend (Vercel)

1. Import the repo in Vercel.
2. Set **Root Directory** to `lesly-frontend`.
3. Add environment variable:

```bash
NEXT_PUBLIC_BACKEND_URL=https://<your-backend-host>/api
```

4. Deploy.

Optional: set the same variable in Project → Settings → Environment Variables for Preview and Production.

## 4. Bot

On the machine running the bot:

```bash
cp .env.example .env
# TELEGRAM_TOKEN, CHAT_ID, Coinbase keys, etc.
BACKEND_API_URL=https://<your-backend-host>/api
DRY_RUN=true
```

```bash
pip install -r requirements.txt
python3 btc_bot.py
```

The bot will POST signals, market snapshots, AI decisions, and closed trades to the backend.

## Local development

Terminal 1 — backend:

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
cd lesly-frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api npm run dev
```

Terminal 3 — bot (optional):

```bash
BACKEND_API_URL=http://localhost:8000/api python3 btc_bot.py
```

Default local DB: `sqlite+aiosqlite:///./lesly.db` in the `backend/` folder.

## Security notes

- Never commit `.env` files with real secrets.
- In production, `POST /api/db/init` is disabled.
- Set `CORS_ORIGINS` to your real frontend URL only.
- Keep `DRY_RUN=true` until you intentionally enable live trading.
