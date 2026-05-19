# Lesly Frontend Architecture

## Role

Next.js 14 dashboard that **displays** data from the FastAPI backend. It does not run trading logic.

Signal generation runs in `../btc_bot.py`. The backend stores and serves data.

## Stack

- Next.js 14 (App Router)
- React 18 + TypeScript
- Tailwind CSS

## Live data

All dashboard panels poll the backend every **3 seconds** via `lib/usePolling.ts`:

| Component | Endpoint |
|-----------|----------|
| `Hero.tsx` | `/market/live`, `/ai/status` |
| `SignalBoard.tsx` | `/signals` |
| `MarketSnapshotPanel.tsx` | `/market/snapshots` |
| `TradeHistoryPanel.tsx` | `/trades` |
| `PerformancePanel.tsx` | `/ai/performance` |
| `AiLogs.tsx` | `/logs` (from `ai_decisions` table) |
| `AiStatusPanel.tsx` | `/ai/status` |

## Configuration

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api
```

See `../DEPLOYMENT.md` for Vercel deployment.

## Local development

```bash
npm install
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api npm run dev
```

Ensure the backend is running on port 8000 and optionally `btc_bot.py` with `BACKEND_API_URL` set.

## Note on TradingPanel chart

The candle chart in `TradingPanel.tsx` is a visual placeholder. Live price, signal, and support/resistance come from the API.
