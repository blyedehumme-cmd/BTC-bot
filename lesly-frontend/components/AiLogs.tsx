'use client';

import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../lib/api';

type AiLog = {
  time: string;
  message: string;
  severity?: string;
  detail?: string;
};

export default function AiLogs() {
  const [logs, setLogs] = useState<AiLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLogs() {
      try {
        const response = await fetch(`${API_BASE_URL}/logs`);
        if (!response.ok) {
          throw new Error('Could not load logs');
        }
        const data: AiLog[] = await response.json();
        setLogs(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }

    fetchLogs();
  }, []);

  return (
    <div className="rounded-[32px] border border-slate-800 bg-surface/90 p-8 shadow-glow backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.26em] text-slate-400">AI Decision Logs</p>
          <h3 className="mt-3 text-3xl font-semibold text-white">Latest Analysis Feed</h3>
        </div>
        <span className="rounded-full bg-glow/10 px-4 py-2 text-sm font-semibold text-glow">Paper Trade Only</span>
      </div>
      <div className="mt-8 space-y-4">
        {loading && <p className="text-slate-300">Loading AI logs...</p>}
        {error && <p className="text-rose-400">{error}</p>}
        {!loading && !error && logs.length === 0 && <p className="text-slate-400">No logs found.</p>}
        {logs.map((log) => (
          <div key={log.time} className="rounded-3xl border border-slate-800 bg-[#07101d]/90 p-5 text-sm text-slate-300 shadow-inner">
            <div className="flex items-center justify-between gap-4 text-slate-500">
              <span>{log.time}</span>
              <span className="rounded-full bg-slate-900/70 px-3 py-1 text-xs uppercase tracking-[0.2em]">{log.severity ?? 'AI Log'}</span>
            </div>
            <p className="mt-3 text-slate-200">{log.message}</p>
            {log.detail && <p className="mt-2 text-sm text-slate-400">{log.detail}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
