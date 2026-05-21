import { fetchJson, postJson } from './usePolling';

export type Signal = {
  id: number;
  symbol: string;
  timeframe: string;
  direction: string;
  confidence_score: number;
  risk_level: string;
  market_condition: string;
  approved: boolean;
  explanation: string;
  created_at: string;
};

export type MarketSnapshot = {
  symbol: string;
  timeframe: string;
  price: number;
  trend: string;
  support: number;
  resistance: number;
  volume: number;
  updated_at: string;
};

export type Trade = {
  id: number;
  signal_id: number;
  entry_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  target_price: number | null;
  closed_price: number | null;
  result_pct: number | null;
  status: string;
  opened_at: string;
  closed_at: string | null;
  drawdown_pct: number | null;
  notes: string | null;
};

export type Performance = {
  total_trades: number;
  total_signals: number;
  wins: number;
  losses: number;
  win_rate: number;
  average_return: number;
  max_drawdown: number;
};

export type AiLog = {
  time: string;
  timestamp?: string;
  message: string;
  severity?: string;
  detail?: string;
};

export type AiStatus = {
  engine_status: string;
  mode: string;
  last_signal: string;
  confidence: number;
  risk_level: string;
  last_analysis_time: string;
  backend_connected: boolean;
};

export type LiveMarket = {
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

export type BotControl = {
  active: boolean;
  mode: string;
  updated_at: string;
  updated_by: string;
  note: string | null;
};

export const fetchSignals = () => fetchJson<Signal[]>('/signals');
export const fetchMarketSnapshots = () => fetchJson<MarketSnapshot[]>('/market/snapshots');
export const fetchTrades = () => fetchJson<Trade[]>('/trades');
export const fetchPerformance = () => fetchJson<Performance>('/ai/performance');
export const fetchAiLogs = () => fetchJson<AiLog[]>('/logs');
export const fetchAiStatus = () => fetchJson<AiStatus>('/ai/status');
export const fetchLiveMarket = () => fetchJson<LiveMarket>('/market/live');
export const fetchBotControl = () => fetchJson<BotControl>('/bot/status');
export const startBot = () => postJson<BotControl>('/bot/start');
export const stopBot = () => postJson<BotControl>('/bot/stop');
