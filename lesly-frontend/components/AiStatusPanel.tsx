'use client';

import { useEffect, useState } from 'react';

type AiStatus = {
  engine: string;
  paper_mode: boolean;
  last_decision: string;
  approved_signals: number;
  rejected_signals: number;
  risk_level: string;
  explanation: string;
  last_updated: string;
};

export default function AiStatusPanel() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const response = await fetch('http://localhost:8000/api/ai/status');
        if (!response.ok) {
          throw new Error('Unable to fetch AI status');
        }
        const data: AiStatus = await response.json();
        setStatus(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }

    fetchStatus();
  }, []);

  return (
    <div className="rounded-[32px] border border-slate-800 bg-surface/90 p-8 shadow-glow backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">AI Dashboard</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">AI Engine Overview</h3>
        </div>
        <span className="rounded-full bg-glow/10 px-4 py-2 text-sm font-semibold text-glow">Live Feed</span>
      </div>
      <div className="mt-8">
        {loading && <p className="text-slate-300">Loading AI status...</p>}
        {error && <p className="text-rose-400">{error}</p>}
        {status && (
          <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-3xl bg-[#07101d]/90 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Engine</p>
                <p className="mt-2 text-xl font-semibold text-white">{status.engine}</p>
              </div>
              <div className="rounded-3xl bg-[#07101d]/90 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Risk Level</p>
                <p className="mt-2 text-xl font-semibold text-white">{status.risk_level}</p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl bg-[#07101d]/90 p-5 text-center">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Approved</p>
                <p className="mt-2 text-2xl font-semibold text-glow">{status.approved_signals}</p>
              </div>
              <div className="rounded-3xl bg-[#07101d]/90 p-5 text-center">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Rejected</p>
                <p className="mt-2 text-2xl font-semibold text-rose-400">{status.rejected_signals}</p>
              </div>
              <div className="rounded-3xl bg-[#07101d]/90 p-5 text-center">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Paper Mode</p>
                <p className="mt-2 text-2xl font-semibold text-white">{status.paper_mode ? 'Active' : 'Disabled'}</p>
              </div>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-[#091229]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Last Decision</p>
              <p className="mt-2 text-white">{status.last_decision}</p>
              <p className="mt-3 text-sm text-slate-400">{status.explanation}</p>
              <p className="mt-4 text-xs uppercase tracking-[0.24em] text-slate-500">Updated at {new Date(status.last_updated).toLocaleTimeString()}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
