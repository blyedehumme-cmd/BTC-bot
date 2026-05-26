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
  symbol?: string;
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
  equity_curve?: Array<{
    time: string;
    equity: number;
    trade_id: number;
    result_pct: number;
  }>;
  monthly_stats?: Array<{
    month: string;
    trades: number;
    wins: number;
    losses: number;
    pnl_pct: number;
    win_rate: number;
  }>;
};

export type AiLog = {
  time: string;
  timestamp?: string;
  message: string;
  severity?: string;
  detail?: string;
  condition_snapshot?: string;
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
  asset?: string;
  asset_name?: string;
  exchange?: string;
  timeframe?: string;
  price: number;
  change_1h_pct: number;
  signal: string;
  confidence: number;
  support: number;
  resistance: number;
  trend: string;
  adx?: number;
  atr?: number;
  volume?: number;
  volume_ratio?: number;
  candles?: Array<{
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
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

export type ManualCloseResponse = {
  accepted: boolean;
  symbol: string;
  requested_at: string;
  message: string;
};

export type StopLossUpdateResponse = ManualCloseResponse & {
  stop_loss?: number;
};

export type LeslyUser = {
  id: number;
  email: string;
  name: string;
  paper_trading: boolean;
  is_active: boolean;
  created_at: string;
};

export type AuthToken = {
  access_token: string;
  token_type: string;
  user: LeslyUser;
};

export type ExchangeAccount = {
  id: number;
  exchange: string;
  account_label: string;
  permissions: string;
  dry_run: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  api_key_preview: string;
  has_secret: boolean;
  has_passphrase: boolean;
};

export const fetchSignals = () => fetchJson<Signal[]>('/signals');
export const fetchMarketSnapshots = () => fetchJson<MarketSnapshot[]>('/market/snapshots');
export const fetchTrades = () => fetchJson<Trade[]>('/trades');
export const fetchPerformance = () => fetchJson<Performance>('/ai/performance');
export const fetchAiLogs = () => fetchJson<AiLog[]>('/logs');
export const fetchAiStatus = () => fetchJson<AiStatus>('/ai/status');
export const fetchLiveMarket = (timeframe = '1H', symbol = 'BTC') => (
  fetchJson<LiveMarket>(`/market/live?timeframe=${encodeURIComponent(timeframe)}&symbol=${encodeURIComponent(symbol)}`)
);
export const fetchBotControl = () => fetchJson<BotControl>('/bot/status');
export const startBot = () => postJson<BotControl>('/bot/start');
export const stopBot = () => postJson<BotControl>('/bot/stop');
export const closePosition = (symbol: string) => postJson<ManualCloseResponse>('/bot/close-position', { symbol });
export const updateStopLoss = (symbol: string, stopLoss: number) => (
  postJson<StopLossUpdateResponse>('/bot/update-stop-loss', { symbol, stop_loss: stopLoss })
);
export const registerUser = (payload: { email: string; name: string; password: string }) => (
  postJson<AuthToken>('/auth/register', payload)
);
export const loginUser = (payload: { email: string; password: string }) => postJson<AuthToken>('/auth/login', payload);
export const fetchCurrentUser = () => fetchJson<LeslyUser>('/auth/me');
export const fetchExchangeAccounts = () => fetchJson<ExchangeAccount[]>('/auth/exchange-accounts');
export const saveExchangeAccount = (payload: {
  exchange: string;
  api_key: string;
  api_secret: string;
  passphrase?: string;
  account_label?: string;
  dry_run?: boolean;
}) => postJson<ExchangeAccount>('/auth/exchange-accounts', payload);
