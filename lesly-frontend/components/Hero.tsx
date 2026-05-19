'use client';

import { useEffect, useState } from 'react';
import TradingPanel from './TradingPanel';
import { API_BASE_URL } from '../lib/api';

type LiveMarket = {
  symbol: string;
  price: number;
  change_1h_pct: number;
  signal: string;
  confidence: number;
  support: number;
  resistance: number;
  trend: string;
  updated_at: string;
  backend_connected: boolean;
};

type AiStatus = {
  engine_status: string;
  mode: string;
  last_signal: string;
  confidence: number;
  last_analysis_time: string;
  backend_connected: boolean;
};

export default function Hero() {
  const [liveMarket, setLiveMarket] = useState<LiveMarket | null>(null);
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log('Frontend API_BASE_URL:', API_BASE_URL);

    let intervalId: NodeJS.Timeout;

    async function fetchDashboardData() {
      try {
        const [marketRes, aiRes] = await Promise.all([
          fetch(`${API_BASE_URL}/market/live`),
          fetch(`${API_BASE_URL}/ai/status`),
        ]);

        if (!marketRes.ok || !aiRes.ok) {
          throw new Error('Backend offline');
        }

        const marketData = await marketRes.json();
        const aiData = await aiRes.json();

        setLiveMarket(marketData);
        setAiStatus(aiData);
        setError(null);
      } catch (err) {
        setError('Backend offline');
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
    intervalId = setInterval(fetchDashboardData, 5000);
    return () => clearInterval(intervalId);
  }, []);

  const priceLabel = liveMarket ? `$${liveMarket.price.toLocaleString()}` : '--';
  const priceChange = liveMarket ? `${liveMarket.change_1h_pct.toFixed(2)}% ${liveMarket.change_1h_pct >= 0 ? '↑' : '↓'}` : 'Live unavailable';
  const signalLabel = liveMarket?.signal ?? 'WAIT';
  const confidenceLabel = liveMarket ? `${liveMarket.confidence}%` : '—';
  const supportLabel = liveMarket ? `$${liveMarket.support.toLocaleString()}` : '—';
  const resistanceLabel = liveMarket ? `$${liveMarket.resistance.toLocaleString()}` : '—';
  const statusLabel = aiStatus?.engine_status ?? 'Offline';
  const modeLabel = aiStatus?.mode.replace('_', ' ') ?? 'PAPER TRADING';

  return (
    <section id="dashboard" className="relative overflow-hidden rounded-[40px] border border-slate-800 bg-surface/90 px-6 py-10 shadow-glow backdrop-blur-xl sm:px-10 lg:px-14">
      <div className="absolute inset-0 bg-neon-grid opacity-30" />
      <div className="relative grid gap-10 lg:grid-cols-[1fr_0.95fr] lg:items-center">
        <div className="space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-glow/30 bg-glow/5 px-4 py-2 text-xs uppercase tracking-[0.3em] text-glow shadow-glow">
            Paper Trading · AI-Driven Signals
          </div>
          <div className="space-y-6">
            <h1 className="max-w-3xl text-5xl font-semibold tracking-tight text-white sm:text-6xl">
              Automated AI Crypto Trading 24/7
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-300">
              Multi-timeframe analysis, intelligent risk management and real-time simulated trading using live market prices.
            </p>
          </div>
          <div className="flex flex-col gap-4 sm:flex-row">
            <a href="#dashboard" className="inline-flex items-center justify-center rounded-full bg-glow px-7 py-3 text-sm font-semibold text-slate-950 shadow-glow hover:bg-glow/90">
              Launch Dashboard
            </a>
            <a href="#signals" className="inline-flex items-center justify-center rounded-full border border-slate-700 bg-white/5 px-7 py-3 text-sm text-slate-200 hover:border-glow hover:text-white">
              View Live Signals
            </a>
          </div>
          <p className="text-xs text-slate-500">
            Using backend: <span className="text-slate-200">{API_BASE_URL}</span>
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-3xl border border-slate-800 bg-[#06101c] p-5 shadow-glow">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-400">BTC Price</p>
              <p className="mt-3 text-3xl font-semibold text-white">{priceLabel}</p>
              <p className="mt-2 text-sm text-slate-400">{!loading && !liveMarket ? 'Backend offline' : `${priceChange} · Paper Mode`}</p>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-300">
                <span className="rounded-full bg-slate-900/70 px-3 py-1">Support {supportLabel}</span>
                <span className="rounded-full bg-slate-900/70 px-3 py-1">Resistance {resistanceLabel}</span>
              </div>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-[#06101c] p-5 shadow-glow">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-400">AI Status</p>
              <p className="mt-3 text-3xl font-semibold text-glow">{statusLabel}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
                <span className="rounded-full bg-slate-900/70 px-3 py-1">{signalLabel} Signal</span>
                <span className="rounded-full bg-slate-900/70 px-3 py-1">Confidence {confidenceLabel}</span>
                <span className="rounded-full bg-slate-900/70 px-3 py-1">{modeLabel}</span>
              </div>
              {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
            </div>
          </div>
        </div>
        <TradingPanel signal={liveMarket?.signal} price={liveMarket?.price} />
      </div>
    </section>
  );
}
