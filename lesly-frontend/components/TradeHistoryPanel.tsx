'use client';

import { useCallback } from 'react';
import { fetchTrades, type Trade } from '../lib/pollingFetchers';
import { usePolling } from '../lib/usePolling';

export default function TradeHistoryPanel() {
  const fetcher = useCallback(() => fetchTrades(), []);
  const { data: trades, loading, error } = usePolling<Trade[]>(fetcher);

  return (
    <div className="rounded-[32px] border border-slate-800 bg-surface/90 p-8 shadow-glow backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Trade History</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">Paper Trade Ledger</h3>
        </div>
        <span className="rounded-full bg-glow/10 px-4 py-2 text-sm font-semibold text-glow">Closed Trades</span>
      </div>
      <div className="mt-8 space-y-4">
        {loading && <p className="text-slate-300">Loading trade history...</p>}
        {error && <p className="text-rose-400">{error}</p>}
        {!loading && (trades?.length ?? 0) === 0 && <p className="text-slate-400">No closed trades available yet.</p>}
        {(trades ?? []).map((trade) => (
          <div key={trade.id} className="rounded-3xl border border-slate-800 bg-[#07101d]/90 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
              <span>Trade #{trade.id}</span>
              <span>{trade.status}</span>
              <span>{new Date(trade.closed_at ?? trade.opened_at).toLocaleString()}</span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Entry</p>
                <p className="mt-2 text-lg font-semibold text-white">${trade.entry_price.toFixed(2)}</p>
              </div>
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Closed</p>
                <p className="mt-2 text-lg font-semibold text-white">${trade.closed_price?.toFixed(2) ?? '—'}</p>
              </div>
              <div className="rounded-3xl bg-[#06131f]/90 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Return</p>
                <p className={`mt-2 text-lg font-semibold ${trade.result_pct !== null && trade.result_pct >= 0 ? 'text-green-400' : 'text-rose-400'}`}>
                  {trade.result_pct !== null ? `${trade.result_pct.toFixed(2)}%` : '—'}
                </p>
              </div>
            </div>
            <p className="mt-4 text-slate-300">Notes: {trade.notes ?? 'No notes'}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
