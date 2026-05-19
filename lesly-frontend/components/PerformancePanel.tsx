'use client';

import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../lib/api';

type Performance = {
  total_signals: number;
  wins: number;
  losses: number;
  win_rate: number;
  average_return: number;
  max_drawdown: number;
};

export default function PerformancePanel() {
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPerformance() {
      try {
        const response = await fetch(`${API_BASE_URL}/ai/performance`);
        if (!response.ok) {
          throw new Error('Unable to fetch performance data');
        }
        const data: Performance = await response.json();
        setPerformance(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }

    fetchPerformance();
  }, []);

  return (
    <div className="rounded-[32px] border border-slate-800 bg-surface/90 p-8 shadow-glow backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">AI Performance</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">Strategy Summary</h3>
        </div>
        <span className="rounded-full bg-glow/10 px-4 py-2 text-sm font-semibold text-glow">Paper Only</span>
      </div>
      <div className="mt-8">
        {loading && <p className="text-slate-300">Loading performance metrics...</p>}
        {error && <p className="text-rose-400">{error}</p>}
        {performance && (
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-3xl bg-[#07101d]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Total Signals</p>
              <p className="mt-3 text-3xl font-semibold text-white">{performance.total_signals}</p>
            </div>
            <div className="rounded-3xl bg-[#07101d]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Win Rate</p>
              <p className="mt-3 text-3xl font-semibold text-glow">{performance.win_rate}%</p>
            </div>
            <div className="rounded-3xl bg-[#07101d]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Avg Return</p>
              <p className="mt-3 text-3xl font-semibold text-white">{performance.average_return}%</p>
            </div>
            <div className="rounded-3xl bg-[#07101d]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Wins</p>
              <p className="mt-3 text-3xl font-semibold text-green-400">{performance.wins}</p>
            </div>
            <div className="rounded-3xl bg-[#07101d]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Losses</p>
              <p className="mt-3 text-3xl font-semibold text-rose-400">{performance.losses}</p>
            </div>
            <div className="rounded-3xl bg-[#07101d]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Max Drawdown</p>
              <p className="mt-3 text-3xl font-semibold text-white">{performance.max_drawdown}%</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
