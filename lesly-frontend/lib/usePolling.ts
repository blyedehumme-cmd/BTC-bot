'use client';

import { useCallback, useEffect, useState } from 'react';
import { API_BASE_URL } from './api';

export const POLL_INTERVAL_MS = 3000;

type PollingState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = POLL_INTERVAL_MS,
): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
    } catch {
      setError('Backend offline');
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    run();
    const intervalId = setInterval(run, intervalMs);
    return () => clearInterval(intervalId);
  }, [run, intervalMs]);

  return { data, loading, error };
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error('Backend offline');
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, payload: unknown = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error('Backend offline');
  }
  return response.json() as Promise<T>;
}

function authHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = window.localStorage.getItem('lesly_access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}
