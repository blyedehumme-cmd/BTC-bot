'use client';

import { useCallback } from 'react';
import { fetchMarketSnapshots, type MarketSnapshot } from '../lib/pollingFetchers';
import { formatNewYorkTime } from '../lib/time';
import { usePolling } from '../lib/usePolling';

export default function MarketSnapshotPanel() {
  const fetcher = useCallback(() => fetchMarketSnapshots(), []);
  const { data: snapshots, loading, error } = usePolling<MarketSnapshot[]>(fetcher);

  return (
    <div className="rounded-[32px] border border-slate-800 bg-surface/90 p-8 shadow-glow backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Market Snapshot</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">Live Market Overview</h3>
        </div>
        <span className="rounded-full bg-glow/10 px-4 py-2 text-sm font-semibold text-glow">Paper Data</span>
      </div>
      <div className="mt-8 space-y-4">
        {loading && <p className="text-slate-300">Loading market snapshots...</p>}
        {error && <p className="text-rose-400">{error}</p>}
        {!loading && (snapshots?.length ?? 0) === 0 && <p className="text-slate-400">No market data available.</p>}
        {(snapshots ?? []).map((snapshot) => (
          <div key={`${snapshot.symbol}-${snapshot.timeframe}`} className="rounded-3xl border border-slate-800 bg-[#07101d]/90 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
              <span>{snapshot.symbol}</span>
              <span>{snapshot.timeframe}</span>
              <span>{snapshot.trend}</span>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Price</p>
                <p className="mt-2 text-2xl font-semibold text-white">${snapshot.price.toLocaleString()}</p>
              </div>
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Volume</p>
                <p className="mt-2 text-2xl font-semibold text-glow">{snapshot.volume.toLocaleString()}</p>
              </div>
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Support</p>
                <p className="mt-2 text-xl font-semibold text-slate-100">${snapshot.support.toLocaleString()}</p>
              </div>
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Resistance</p>
                <p className="mt-2 text-xl font-semibold text-slate-100">${snapshot.resistance.toLocaleString()}</p>
              </div>
            </div>
            <p className="mt-4 text-sm text-slate-400">Updated at {formatNewYorkTime(snapshot.updated_at)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
