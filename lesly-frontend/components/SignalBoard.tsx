'use client';

import { useCallback } from 'react';
import { fetchSignals, type Signal } from '../lib/pollingFetchers';
import { usePolling } from '../lib/usePolling';

export default function SignalBoard() {
  const fetcher = useCallback(() => fetchSignals(), []);
  const { data: signals, loading, error } = usePolling<Signal[]>(fetcher);

  return (
    <div className="rounded-[32px] border border-slate-800 bg-surface/90 p-8 shadow-glow backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Live Paper Signals</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">Backend-connected Signal Feed</h3>
        </div>
        <span className="rounded-full bg-glow/10 px-4 py-2 text-sm font-semibold text-glow">Paper Mode</span>
      </div>
      <div className="mt-8 space-y-4">
        {loading && <p className="text-slate-300">Loading simulated signals...</p>}
        {error && <p className="text-rose-400">{error}</p>}
        {!loading && !error && (signals?.length ?? 0) === 0 && (
          <p className="text-slate-400">No paper signals available yet.</p>
        )}
        {(signals ?? []).map((signal) => (
          <div key={signal.id} className="rounded-3xl border border-slate-800 bg-[#07101d]/90 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
              <span>{signal.symbol}</span>
              <span>{signal.timeframe}</span>
              <span>{signal.direction}</span>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-slate-950/80 px-3 py-1 text-xs uppercase tracking-[0.24em] text-slate-300">
                Confidence {signal.confidence_score}%
              </span>
              <span className="rounded-full bg-slate-950/80 px-3 py-1 text-xs uppercase tracking-[0.24em] text-slate-300">
                {signal.risk_level}
              </span>
              <span className="rounded-full bg-slate-950/80 px-3 py-1 text-xs uppercase tracking-[0.24em] text-slate-300">
                {signal.market_condition}
              </span>
            </div>
            <p className="mt-4 text-slate-300">{signal.explanation}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
