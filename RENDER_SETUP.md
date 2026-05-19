# Render + Neon + Vercel — checklist

Use this after pushing the latest code to GitHub.

## 1. Render (backend)

**Service settings**

| Setting | Value |
|---------|--------|
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/health` |

**Environment variables** (you already have `DATABASE_URL` from Neon)

| Key | Value |
|-----|--------|
| `DATABASE_URL` | *(Neon connection string — already set)* |
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | Long random string |
| `FRONTEND_URL` | Your Vercel URL, e.g. `https://btc-bot.vercel.app` |
| `CORS_ORIGINS` | Same as `FRONTEND_URL` (comma-separated if multiple) |
| `CORS_ALLOW_VERCEL_PREVIEWS` | `true` |

On deploy, the app runs **Alembic migrations automatically** on startup.

**Verify**

```bash
curl https://<your-service>.onrender.com/api/health
```

Expected: `"database": "connected"`, `"status": "healthy"`.

## 2. Vercel (frontend)

| Setting | Value |
|---------|--------|
| Root Directory | `lesly-frontend` |
| `NEXT_PUBLIC_BACKEND_URL` | `https://<your-service>.onrender.com/api` |

Redeploy after setting the variable.

## 3. Bot (local or Render worker)

```bash
BACKEND_API_URL=https://<your-service>.onrender.com/api
DRY_RUN=true
python3 btc_bot.py
```

The bot POSTs signals, snapshots, AI decisions, and trades — the dashboard will populate within a few seconds.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS error in browser | Set `FRONTEND_URL` / `CORS_ORIGINS` to exact Vercel URL; keep `CORS_ALLOW_VERCEL_PREVIEWS=true` |
| `database: error` in health | Check Neon URL includes `?sslmode=require`; confirm IP allowlist (Neon usually allows all) |
| Empty dashboard | Run `btc_bot.py` with `BACKEND_API_URL` pointing to Render |
| 502 on Render free tier | Service may be sleeping; first request wakes it (~30s) |
