'use client';

import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../lib/api';

type AiStatus = {
  engine_status: string;
  mode: string;
  last_signal: string;
  confidence: number;
  last_analysis_time: string;
  backend_connected: boolean;
};

export default function AiStatusPanel() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const response = await fetch(`${API_BASE_URL}/ai/status`);
        if (!response.ok) {
          throw new Error('Backend offline');
        }
        const data: AiStatus = await response.json();
        setStatus(data);
      } catch (err) {
        setError('Backend offline');
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
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Engine Status</p>
                <p className="mt-2 text-xl font-semibold text-white">{status.engine_status}</p>
              </div>
              <div className="rounded-3xl bg-[#07101d]/90 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Mode</p>
                <p className="mt-2 text-xl font-semibold text-white">{status.mode}</p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl bg-[#07101d]/90 p-5 text-center">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Last Signal</p>
                <p className="mt-2 text-2xl font-semibold text-glow">{status.last_signal}</p>
              </div>
              <div className="rounded-3xl bg-[#07101d]/90 p-5 text-center">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Confidence</p>
                <p className="mt-2 text-2xl font-semibold text-green-400">{status.confidence}%</p>
              </div>
              <div className="rounded-3xl bg-[#07101d]/90 p-5 text-center">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Backend</p>
                <p className="mt-2 text-2xl font-semibold text-white">{status.backend_connected ? 'Connected' : 'Offline'}</p>
              </div>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-[#091229]/90 p-5">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Last Analysis</p>
              <p className="mt-2 text-white">{new Date(status.last_analysis_time).toLocaleString()}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
