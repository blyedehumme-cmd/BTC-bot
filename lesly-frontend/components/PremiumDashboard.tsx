'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  closePosition,
  fetchBotControl,
  fetchAiLogs,
  fetchAiStatus,
  fetchLiveMarket,
  fetchMarketSnapshots,
  fetchPerformance,
  fetchSignals,
  fetchTrades,
  fetchUserPaperRuntime,
  startBot,
  stopBot,
  updateStopLoss,
  type AiLog,
  type AiStatus,
  type BotControl,
  type LiveMarket,
  type MarketSnapshot,
  type Performance,
  type Signal,
  type Trade,
  type UserPaperRuntime,
} from '../lib/pollingFetchers';
import { formatNewYorkDateTime, formatNewYorkTime } from '../lib/time';
import { usePolling } from '../lib/usePolling';

const navItems = ['Dashboard', 'Señales', 'Operaciones', 'Backtesting', 'Riesgo', 'Configuración', 'IA análisis', 'Historial', 'IA chat'];
const timeframes = [
  { label: '15', value: '15M' },
  { label: '30', value: '30M' },
  { label: '1', value: '1H' },
  { label: '4', value: '4H' },
  { label: '1D', value: '1D' },
];
const cryptoMarkets = [
  { symbol: 'BTC', display: 'BTCUSD', name: 'Bitcoin / US Dollar' },
  { symbol: 'ETH', display: 'ETHUSD', name: 'Ethereum / US Dollar' },
];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const paperStartingBalance = Number(process.env.NEXT_PUBLIC_PAPER_STARTING_BALANCE ?? 5000);
const POSITION_STATUS_MAX_AGE_MS = 15 * 60 * 1000;

type Candle = {
  time?: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
};

type StrategyCheck = {
  label: string;
  status: string;
  value?: string | number;
  detail?: string;
};

type DecisionSnapshot = {
  signal?: string;
  confidence?: number;
  trend_1h?: string;
  adx?: number;
  volume_ratio?: number;
  atr?: number;
  volatility_ratio?: number;
  hmm_regime?: number | string | null;
  hmm_regime_label?: string | null;
  hmm_source?: string | null;
  strategy_checks?: StrategyCheck[];
  blocked_reasons?: string[];
  ai_called?: boolean;
  ai_rate_limited?: boolean;
  supervisor_decision?: {
    approved?: boolean;
    action?: string;
    reason?: string;
    agents?: Array<{
      name?: string;
      status?: string;
      reason?: string;
      data?: {
        regime?: number | string | null;
        label?: string | null;
      };
    }>;
  };
  open_position?: {
    status?: string;
    symbol?: string;
    entry_timeframe?: string;
    side?: string;
    entry_price?: number;
    mark_price?: number;
    position_size?: number;
    position_usd?: number;
    margin_reserved?: number;
    unrealized_pnl?: number;
    unrealized_pnl_pct?: number;
    stop_loss?: number;
    take_profit?: number;
    leverage?: number;
    confidence?: number;
    opened_at?: string;
    reason?: string;
  };
  open_positions?: NonNullable<DecisionSnapshot['open_position']>[];
  paper_starting_balance?: number;
  paper_balance?: number;
  available_balance?: number;
  margin_reserved?: number;
  open_notional?: number;
  unrealized_pnl?: number;
  paper_equity?: number;
  realized_pnl?: number;
};

function formatMoney(value?: number | null) {
  return typeof value === 'number' && Number.isFinite(value) ? money.format(value) : '—';
}

function formatPct(value?: number | null) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(2)}%` : '—';
}

function signalTone(signal?: string | null) {
  const normalized = (signal || 'WAIT').toUpperCase();
  if (normalized === 'LONG') return 'text-emerald-300 border-emerald-400/40 bg-emerald-500/10 shadow-[0_0_28px_rgba(16,185,129,0.18)]';
  if (normalized === 'SHORT') return 'text-rose-300 border-rose-400/40 bg-rose-500/10 shadow-[0_0_28px_rgba(244,63,94,0.18)]';
  return 'text-cyan-200 border-cyan-400/40 bg-cyan-500/10 shadow-[0_0_28px_rgba(34,211,238,0.16)]';
}

function latest<T>(items?: T[] | null): T | null {
  return items && items.length > 0 ? items[0] : null;
}

function matchesCrypto(symbol: string | undefined | null, crypto: string) {
  if (!symbol) return false;
  return symbol.toUpperCase().includes(crypto.toUpperCase());
}

function latestForCrypto<T extends { symbol?: string }>(items: T[] | undefined | null, crypto: string): T | null {
  return (items ?? []).find((item) => matchesCrypto(item.symbol, crypto)) ?? null;
}

function snapshotMatchesCrypto(snapshot: DecisionSnapshot, crypto: string) {
  return (
    matchesCrypto(snapshot.open_position?.symbol, crypto)
    || matchesCrypto((snapshot as DecisionSnapshot & { symbol?: string }).symbol, crypto)
    || matchesCrypto((snapshot as DecisionSnapshot & { trade_symbol?: string }).trade_symbol, crypto)
  );
}

function isFreshLog(log: AiLog, maxAgeMs = POSITION_STATUS_MAX_AGE_MS) {
  if (!log.timestamp) return false;
  const timestamp = new Date(log.timestamp).getTime();
  return Number.isFinite(timestamp) && Date.now() - timestamp <= maxAgeMs;
}

function positionExitAlreadyCrossed(position: NonNullable<DecisionSnapshot['open_position']> | null, markPrice: number) {
  if (!position || !Number.isFinite(markPrice) || markPrice <= 0) return false;
  const side = String(position.side ?? '').toUpperCase();
  const stop = Number(position.stop_loss ?? 0);
  const take = Number(position.take_profit ?? 0);
  const tolerance = markPrice * 0.0005;
  if (side === 'LONG') {
    return (take > 0 && markPrice >= take + tolerance) || (stop > 0 && markPrice <= stop - tolerance);
  }
  if (side === 'SHORT') {
    return (take > 0 && markPrice <= take - tolerance) || (stop > 0 && markPrice >= stop + tolerance);
  }
  return false;
}

function parseDecisionSnapshot(logs?: AiLog[] | null, crypto?: string): DecisionSnapshot | null {
  for (const log of logs ?? []) {
    if (!log.condition_snapshot) continue;
    try {
      const snapshot = JSON.parse(log.condition_snapshot) as DecisionSnapshot;
      if (!crypto || snapshotMatchesCrypto(snapshot, crypto)) return snapshot;
    } catch {
      continue;
    }
  }
  return null;
}

function parseOpenPositionSnapshot(logs?: AiLog[] | null, crypto?: string): DecisionSnapshot | null {
  for (const log of logs ?? []) {
    if (!log.message?.toLowerCase().includes('paper positions status')) continue;
    if (!isFreshLog(log)) continue;
    if (!log.condition_snapshot) continue;
    try {
      const snapshot = JSON.parse(log.condition_snapshot) as DecisionSnapshot;
      if (Array.isArray(snapshot.open_positions)) {
        const matchingPosition = crypto
          ? snapshot.open_positions.find((position) => matchesCrypto(position.symbol, crypto))
          : snapshot.open_positions[0];
        if (matchingPosition) return { ...snapshot, open_position: matchingPosition };
        return { ...snapshot, open_position: { status: 'NONE' } };
      }
    } catch {
      continue;
    }
  }
  return null;
}

function parsePaperAccountSnapshot(logs?: AiLog[] | null): DecisionSnapshot | null {
  for (const log of logs ?? []) {
    if (!log.message?.toLowerCase().includes('paper positions status')) continue;
    if (!isFreshLog(log)) continue;
    if (!log.condition_snapshot) continue;
    try {
      const snapshot = JSON.parse(log.condition_snapshot) as DecisionSnapshot;
      if (Array.isArray(snapshot.open_positions) || typeof snapshot.paper_balance === 'number') return snapshot;
    } catch {
      continue;
    }
  }
  return null;
}

function runtimePositionToSnapshot(position: UserPaperRuntime['open_positions'][number]): NonNullable<DecisionSnapshot['open_position']> {
  return {
    status: position.status,
    symbol: position.symbol,
    entry_timeframe: position.timeframe,
    side: position.side,
    entry_price: position.entry_price,
    mark_price: position.mark_price,
    position_size: position.size,
    position_usd: position.notional,
    margin_reserved: position.margin_reserved,
    stop_loss: position.stop_loss ?? undefined,
    take_profit: position.take_profit ?? undefined,
    leverage: position.leverage,
    opened_at: position.opened_at,
    reason: 'Runtime paper del usuario.',
  };
}

function logMatchesCrypto(log: AiLog, crypto: string) {
  const text = `${log.message ?? ''} ${log.detail ?? ''}`.toUpperCase();
  if (text.includes(crypto.toUpperCase())) return true;
  if (!log.condition_snapshot) return false;
  try {
    return snapshotMatchesCrypto(JSON.parse(log.condition_snapshot) as DecisionSnapshot, crypto);
  } catch {
    return false;
  }
}

function hmmContext(snapshot: DecisionSnapshot | null) {
  const hmmAgent = snapshot?.supervisor_decision?.agents?.find((agent) => agent.name === 'hmm');
  const regime = snapshot?.hmm_regime ?? hmmAgent?.data?.regime;
  const label = snapshot?.hmm_regime_label ?? hmmAgent?.data?.label;
  const status = hmmAgent?.status;
  const reason = hmmAgent?.reason;

  if (regime === undefined || regime === null) {
    return {
      regime: 'Sin régimen',
      label: 'Contexto HMM no recibido',
      status: status ?? 'context',
      reason: reason ?? 'HMM está como contexto, no como filtro automático.',
    };
  }

  return {
    regime: `Régimen ${regime}`,
    label: label || 'Régimen estadístico',
    status: status ?? 'context',
    reason: reason ?? 'HMM disponible como contexto; no bloquea operaciones.',
  };
}

function fallbackStrategyChecks(params: { live: LiveMarket | null; snapshot: MarketSnapshot | null; signal: string; confidence: number }): StrategyCheck[] {
  return [
    {
      label: 'Snapshot',
      status: params.live || params.snapshot ? 'pending' : 'block',
      value: params.live || params.snapshot ? 'Mercado conectado' : 'Sin datos',
      detail: params.live || params.snapshot ? 'Esperando matriz detallada del próximo ciclo del bot.' : 'Backend sin snapshot de mercado todavía.',
    },
    {
      label: 'Señal',
      status: 'pending',
      value: params.signal,
      detail: `Última señal visible con confianza ${params.confidence}%.`,
    },
    {
      label: 'Tendencia',
      status: 'pending',
      value: params.live?.trend ?? params.snapshot?.trend ?? 'Pendiente',
      detail: 'Dato live disponible; confirmaciones 1D/4H/1H llegan desde el worker.',
    },
    {
      label: 'Riesgo',
      status: 'pending',
      value: 'Pendiente bot',
      detail: 'ATR, ADX, volumen y volatilidad se llenan cuando btc_bot.py publique condition_snapshot.',
    },
  ];
}

function useLiveClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return now;
}

function makeCandles(price: number, support?: number, resistance?: number, seed = 1): Candle[] {
  if (!price || !Number.isFinite(price)) return [];
  const floor = support && support > 0 ? support : price * 0.985;
  const ceiling = resistance && resistance > 0 ? resistance : price * 1.015;
  const span = Math.max(ceiling - floor, price * 0.01);
  return Array.from({ length: 34 }, (_, index) => {
    const phase = index / 3.4 + seed;
    const base = floor + span * (0.34 + index / 58 + Math.sin(phase) * 0.085);
    const open = base + Math.cos(phase * 1.7) * span * 0.035;
    const close = base + Math.sin(phase * 1.4) * span * 0.045;
    const high = Math.max(open, close) + span * (0.035 + (index % 5) * 0.004);
    const low = Math.min(open, close) - span * (0.028 + (index % 4) * 0.004);
    return { open, close, high, low, volume: 24 + ((index * 11) % 48) };
  });
}

function emaSeries(values: number[], period: number) {
  if (!values.length || period <= 0) return [];
  const k = 2 / (period + 1);
  let current = values[0];
  return values.map((value) => {
    current = value * k + current * (1 - k);
    return current;
  });
}

function macdHistogram(values: number[]) {
  if (values.length < 60) return null;
  const fast = emaSeries(values, 21);
  const slow = emaSeries(values, 50);
  const macdLine = values.map((_, index) => fast[index] - slow[index]);
  const signal = emaSeries(macdLine, 10);
  return macdLine[macdLine.length - 1] - signal[signal.length - 1];
}

function MiniSparkline({ values, tone = 'cyan' }: { values: number[]; tone?: 'cyan' | 'green' | 'red' }) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const points = values.map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${36 - ((value - min) / range) * 30}`).join(' ');
  const color = tone === 'green' ? '#22c55e' : tone === 'red' ? '#ff334e' : '#009dff';
  return (
    <svg className="h-12 w-full overflow-visible" viewBox="0 0 100 40" preserveAspectRatio="none">
      <polyline fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" points={points} />
      <polyline fill="none" stroke={color} strokeOpacity="0.22" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" points={points} />
    </svg>
  );
}

function CandleChart({
  price,
  support,
  resistance,
  timeframe,
  candles: liveCandles,
  exchange,
  label,
  assetName,
  adx,
  atr,
  volumeRatio,
}: {
  price: number;
  support?: number;
  resistance?: number;
  timeframe: string;
  candles?: Candle[];
  exchange?: string;
  label?: string;
  assetName?: string;
  adx?: number;
  atr?: number;
  volumeRatio?: number;
}) {
  const candles = useMemo(() => {
    const clean = (liveCandles ?? []).filter((candle) => [candle.open, candle.high, candle.low, candle.close].every((value) => Number.isFinite(value)));
    return clean.length > 5 ? clean.slice(-54) : makeCandles(price, support, resistance, timeframe.length);
  }, [liveCandles, price, support, resistance, timeframe]);
  const closes = candles.map((candle) => candle.close);
  const highs = candles.map((candle) => candle.high);
  const lows = candles.map((candle) => candle.low);
  const max = Math.max(...highs, price * 1.01);
  const min = Math.min(...lows, price * 0.99);
  const range = Math.max(max - min, 1);
  const widthStep = 100 / Math.max(candles.length - 1, 1);
  const linePoints = (series: number[]) => series
    .map((value, index) => `${index * widthStep},${((max - value) / range) * 100}`)
    .join(' ');
  const ema21 = emaSeries(closes, 21);
  const ema50 = emaSeries(closes, 50);
  const ema100 = emaSeries(closes, 100);
  const macdHist = macdHistogram(closes);
  const levelTop = (level?: number) => {
    if (!level || level <= min || level >= max) return null;
    return ((max - level) / range) * 100;
  };
  const supportTop = levelTop(support);
  const resistanceTop = levelTop(resistance);

  return (
    <div className="premium-card relative h-[360px] overflow-hidden p-4 sm:p-5">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,157,255,0.055)_1px,transparent_1px),linear-gradient(90deg,rgba(0,157,255,0.055)_1px,transparent_1px)] bg-[size:70px_38px]" />
      <div className="relative z-10 mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="panel-label">{label ?? 'BTCUSD'}</p>
          <div className="mt-2 flex flex-wrap items-end gap-3">
            <p className="text-3xl font-semibold text-white sm:text-4xl">{formatMoney(price)}</p>
            <span className="pb-1 text-sm font-semibold text-emerald-300">{exchange ? `${exchange.toUpperCase()} live` : 'Live'}</span>
          </div>
          {assetName && <p className="mt-1 text-xs text-slate-500">{assetName}</p>}
        </div>
        <div className="flex rounded-xl border border-cyan-400/20 bg-black/30 p-1">
          {timeframes.map((item) => (
            <span key={item.value} className={`rounded-lg px-3 py-1.5 text-xs transition ${item.value === timeframe ? 'bg-blue-500 text-white shadow-[0_0_22px_rgba(0,112,255,0.55)]' : 'text-slate-400'}`}>
              {item.label}
            </span>
          ))}
        </div>
      </div>
      <div className="relative z-10 h-[250px]">
        <svg className="pointer-events-none absolute inset-0 z-20 h-full w-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
          {supportTop !== null && <line x1="0" x2="100" y1={supportTop} y2={supportTop} stroke="#22d3ee" strokeWidth="0.45" strokeDasharray="3 3" opacity="0.62" />}
          {resistanceTop !== null && <line x1="0" x2="100" y1={resistanceTop} y2={resistanceTop} stroke="#fb7185" strokeWidth="0.45" strokeDasharray="3 3" opacity="0.62" />}
          <polyline points={linePoints(ema21)} fill="none" stroke="#22c55e" strokeWidth="0.55" strokeLinecap="round" strokeLinejoin="round" opacity="0.92" />
          <polyline points={linePoints(ema50)} fill="none" stroke="#38bdf8" strokeWidth="0.55" strokeLinecap="round" strokeLinejoin="round" opacity="0.88" />
          <polyline points={linePoints(ema100)} fill="none" stroke="#f472b6" strokeWidth="0.55" strokeLinecap="round" strokeLinejoin="round" opacity="0.82" />
        </svg>
        {candles.map((candle, index) => {
          const up = candle.close >= candle.open;
          const x = (index / Math.max(candles.length, 1)) * 100;
          const highTop = ((max - candle.high) / range) * 100;
          const lowTop = ((max - candle.low) / range) * 100;
          const openTop = ((max - candle.open) / range) * 100;
          const closeTop = ((max - candle.close) / range) * 100;
          const bodyTop = Math.min(openTop, closeTop);
          const bodyHeight = Math.max(Math.abs(openTop - closeTop), 2.5);
          return (
            <div key={`${timeframe}-${index}`} className="absolute bottom-0 top-0 animate-rise" style={{ left: `${x}%`, width: `${86 / candles.length}%`, animationDelay: `${index * 18}ms` }}>
              <div className={`absolute left-1/2 w-px -translate-x-1/2 ${up ? 'bg-emerald-400' : 'bg-rose-500'}`} style={{ top: `${highTop}%`, height: `${Math.max(lowTop - highTop, 6)}%` }} />
              <div className={`absolute left-1/2 w-full -translate-x-1/2 rounded-sm ${up ? 'bg-emerald-400 shadow-[0_0_14px_rgba(16,185,129,0.45)]' : 'bg-rose-500 shadow-[0_0_14px_rgba(244,63,94,0.45)]'}`} style={{ top: `${bodyTop}%`, height: `${bodyHeight}%` }} />
              <div className={`absolute bottom-0 left-1/2 w-full -translate-x-1/2 opacity-40 ${up ? 'bg-emerald-500' : 'bg-rose-600'}`} style={{ height: `${Math.min(candle.volume, 72)}px` }} />
            </div>
          );
        })}
        <div className="absolute right-0 top-1/2 rounded-l-lg bg-emerald-500 px-3 py-1 text-xs font-semibold text-white shadow-[0_0_24px_rgba(16,185,129,0.45)]">
          {number.format(price)}
        </div>
        <div className="absolute bottom-2 left-2 z-30 flex flex-wrap gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em]">
          <span className="rounded-full border border-emerald-400/30 bg-black/55 px-2 py-1 text-emerald-300">EMA 21</span>
          <span className="rounded-full border border-sky-400/30 bg-black/55 px-2 py-1 text-sky-300">EMA 50</span>
          <span className="rounded-full border border-pink-400/30 bg-black/55 px-2 py-1 text-pink-300">EMA 100</span>
        </div>
        <div className="absolute right-2 top-2 z-30 flex max-w-[70%] flex-wrap justify-end gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em]">
          <span className="rounded-full border border-cyan-400/25 bg-black/55 px-2 py-1 text-cyan-200">ADX {adx ? number.format(adx) : '—'}</span>
          <span className="rounded-full border border-cyan-400/25 bg-black/55 px-2 py-1 text-cyan-200">ATR {atr ? number.format(atr) : '—'}</span>
          <span className="rounded-full border border-cyan-400/25 bg-black/55 px-2 py-1 text-cyan-200">Vol {volumeRatio ? `${volumeRatio.toFixed(2)}x` : '—'}</span>
          <span className={`rounded-full border bg-black/55 px-2 py-1 ${macdHist === null ? 'border-slate-500/25 text-slate-300' : macdHist >= 0 ? 'border-emerald-400/25 text-emerald-300' : 'border-rose-400/25 text-rose-300'}`}>
            MACD {macdHist === null ? '—' : macdHist >= 0 ? '+' : '-'}
          </span>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  tone = 'cyan',
  values,
  indicatorLabel,
  indicatorValue,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: 'cyan' | 'green' | 'red';
  values?: number[];
  indicatorLabel?: string;
  indicatorValue?: string;
}) {
  const color = tone === 'green' ? 'text-emerald-300' : tone === 'red' ? 'text-rose-300' : 'text-cyan-300';
  const border = tone === 'green' ? 'border-emerald-400/25 bg-emerald-400/10' : tone === 'red' ? 'border-rose-400/25 bg-rose-400/10' : 'border-cyan-400/25 bg-cyan-400/10';
  return (
    <article className={`premium-card metric-card metric-card-${tone} group min-h-[118px] overflow-hidden p-5 transition duration-300 hover:-translate-y-1 hover:border-cyan-300/60 hover:shadow-[0_0_45px_rgba(0,157,255,0.22)]`}>
      <div className="water-line water-line-a" />
      <div className="water-line water-line-b" />
      <div className="relative z-10 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="panel-label">{label}</p>
          <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
          {sub && <p className={`mt-1 text-sm font-semibold ${color}`}>{sub}</p>}
        </div>
        {indicatorLabel && indicatorValue ? (
          <div className={`min-w-[92px] rounded-2xl border px-3 py-2 text-right ${border}`}>
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{indicatorLabel}</p>
            <p className={`mt-1 text-sm font-semibold ${color}`}>{indicatorValue}</p>
          </div>
        ) : values && values.length > 1 ? (
          <div className="w-24 opacity-90 transition group-hover:scale-105">
            <MiniSparkline values={values} tone={tone} />
          </div>
        ) : null}
      </div>
    </article>
  );
}

function CryptoSelector({
  selectedCrypto,
  onChange,
  compact = false,
}: {
  selectedCrypto: string;
  onChange: (symbol: string) => void;
  compact?: boolean;
}) {
  return (
    <label className={`flex items-center gap-3 rounded-xl border border-cyan-400/20 bg-black/35 px-4 py-2 text-sm text-slate-300 shadow-[0_0_24px_rgba(0,157,255,0.08)] ${compact ? 'w-full flex-col items-start gap-2' : 'min-w-[230px]'}`}>
      <span className="text-xs uppercase tracking-[0.18em] text-cyan-300">Criptomoneda</span>
      <select
        value={selectedCrypto}
        onChange={(event) => onChange(event.target.value)}
        className="w-full min-w-0 flex-1 bg-transparent font-semibold text-white outline-none"
      >
        {cryptoMarkets.map((market) => (
          <option key={market.symbol} value={market.symbol} className="bg-slate-950 text-white">
            {market.display} · {market.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Sidebar({ botActive, liveNow, selectedCrypto, onCryptoChange }: { botActive: boolean; liveNow: Date; selectedCrypto: string; onCryptoChange: (symbol: string) => void }) {
  return (
    <aside className="premium-card sticky top-4 hidden h-[calc(100vh-2rem)] w-[250px] shrink-0 overflow-hidden p-4 xl:block">
      <div className="mb-8 flex items-center gap-3 px-2 pt-2">
        <div className="grid h-12 w-12 place-items-center rounded-2xl border border-cyan-300/40 bg-blue-500/15 shadow-[0_0_30px_rgba(0,157,255,0.4)]">
          <span className="text-2xl font-black text-cyan-200">L</span>
        </div>
        <div>
          <p className="text-2xl font-bold tracking-tight text-white">LESLY</p>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">AI Trading Bot</p>
        </div>
      </div>
      <nav className="space-y-2">
        {navItems.map((item, index) => (
          <div key={item} className="space-y-2">
            {item === 'Señales' && <CryptoSelector selectedCrypto={selectedCrypto} onChange={onCryptoChange} compact />}
            <a href={`#${item.toLowerCase().replace(/ /g, '-')}`} className={`nav-item ${index === 0 ? 'nav-item-active' : ''}`}>
              <span className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-sm">{['⌂', '↗', '⇄', '▰', '⬟', '⚙', '✦', '☷', '◌'][index]}</span>
              <span>{item}</span>
              {item === 'IA chat' && <span className="ml-auto rounded-full border border-cyan-400/30 px-2 py-0.5 text-[10px] text-cyan-300">BETA</span>}
            </a>
          </div>
        ))}
      </nav>
      <div className={`absolute bottom-4 left-4 right-4 rounded-2xl border p-4 ${botActive ? 'border-emerald-400/20 bg-emerald-500/10' : 'border-rose-400/20 bg-rose-500/10'}`}>
        <div className={`flex items-center gap-2 text-sm font-semibold ${botActive ? 'text-emerald-300' : 'text-rose-300'}`}><span className={`h-3 w-3 rounded-full ${botActive ? 'bg-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.9)]' : 'bg-rose-400 shadow-[0_0_18px_rgba(244,63,94,0.9)]'}`} /> {botActive ? 'BOT ACTIVO' : 'BOT PAUSADO'}</div>
        <p className="mt-2 text-xs text-slate-400">Modo papel · backend live</p>
        <div className="mt-3 rounded-xl border border-cyan-400/10 bg-black/25 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Hora NY live</p>
          <p className="text-lg font-semibold text-cyan-200">{formatNewYorkTime(liveNow)}</p>
        </div>
      </div>
    </aside>
  );
}

function ControlButtons({ botActive, busy, onStart, onStop }: { botActive: boolean; busy: boolean; onStart: () => void; onStop: () => void }) {
  return (
    <div className="premium-card grid h-full min-h-[118px] grid-cols-2 gap-3 p-4">
      <button className={`energy-button energy-start ${botActive ? 'opacity-70' : ''}`} type="button" onClick={onStart} disabled={busy || botActive}><span>▶</span>{busy ? '...' : 'START BOT'}</button>
      <button className={`energy-button energy-stop ${!botActive ? 'opacity-70' : ''}`} type="button" onClick={onStop} disabled={busy || !botActive}><span>■</span>{busy ? '...' : 'STOP BOT'}</button>
    </div>
  );
}

function SystemStatus({ aiStatus }: { aiStatus: AiStatus | null }) {
  const healthy = aiStatus?.backend_connected !== false;
  const checks = [
    'Conexión API',
    'Análisis de mercado',
    'Gestión de riesgo',
    'Ejecución de órdenes',
    'IA & aprendizaje',
  ];

  return (
    <div className="premium-card h-full p-5">
      <div className="panel-head"><h2>Estado del sistema</h2><span>{healthy ? 'óptimo' : 'alerta'}</span></div>
      <div className="flex flex-col items-center">
        <div className="system-orb h-36 w-36"><span className="h-24 w-24 text-3xl">{healthy ? '100%' : '72%'}</span></div>
        <div className="mt-6 w-full space-y-3 text-sm text-slate-300">
          {checks.map((item) => (
            <p key={item} className="flex items-center gap-3">
              <span className={`grid h-5 w-5 place-items-center rounded ${healthy ? 'bg-emerald-500 text-white' : 'bg-amber-400 text-black'}`}>✓</span>
              {item}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

function StrategyMatrix({ checks, blockedReasons }: { checks: StrategyCheck[]; blockedReasons: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const pending = checks.some((check) => check.status === 'pending');
  const okCount = checks.filter((check) => check.status === 'ok').length;
  const blockCount = checks.filter((check) => check.status !== 'ok' && check.status !== 'pending').length;
  const visibleChecks = expanded ? checks : checks.slice(0, 1);
  const firstCheck = checks[0];
  return (
    <div className="premium-card p-5">
      <div className="panel-head"><h2>Matriz swing</h2><span>{blockedReasons.length ? 'WAIT' : pending ? 'pendiente' : 'alineado'}</span></div>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="mb-4 w-full rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-left transition hover:border-cyan-300/50 hover:bg-cyan-400/15"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Resumen de entrada</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {checks.length ? `${okCount}/${checks.length} confirmaciones OK` : 'Esperando matriz del bot'}
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {firstCheck ? `${firstCheck.label}: ${String(firstCheck.value ?? firstCheck.detail ?? '—')}` : 'Toca aquí cuando llegue el próximo análisis.'}
            </p>
          </div>
          <div className="text-right">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${blockCount ? 'bg-rose-400/15 text-rose-300' : pending ? 'bg-cyan-400/15 text-cyan-300' : 'bg-emerald-400/15 text-emerald-300'}`}>
              {blockCount ? `${blockCount} bloquea` : pending ? 'pendiente' : 'alineado'}
            </span>
            <p className="mt-2 text-xs text-slate-500">{expanded ? 'Ocultar detalle' : 'Ver detalle'}</p>
          </div>
        </div>
      </button>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {checks.length === 0 && <p className="text-sm text-slate-500">Esperando snapshot de estrategia del bot.</p>}
        {visibleChecks.map((check, index) => {
          const ok = check.status === 'ok';
          const isPending = check.status === 'pending';
          const tone = ok
            ? 'border-emerald-400/20 bg-emerald-500/10'
            : isPending
              ? 'border-cyan-400/20 bg-cyan-500/10'
              : 'border-rose-400/20 bg-rose-500/10';
          return (
            <div key={`${check.label}-${index}`} className={`rounded-2xl border p-3 ${tone}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{check.label}</p>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${ok ? 'bg-emerald-400/15 text-emerald-300' : isPending ? 'bg-cyan-400/15 text-cyan-300' : 'bg-rose-400/15 text-rose-300'}`}>{ok ? 'OK' : isPending ? 'PENDIENTE' : 'BLOQUEA'}</span>
              </div>
              <p className="mt-2 text-sm font-semibold text-white">{String(check.value ?? check.detail ?? '—')}</p>
              {check.detail && <p className="mt-1 text-xs text-slate-500">{check.detail}</p>}
            </div>
          );
        })}
      </div>
      {!expanded && checks.length > 1 && (
        <p className="mt-3 text-xs text-slate-500">Hay {checks.length - 1} validaciones más ocultas. Toca el resumen para verlas.</p>
      )}
      {expanded && blockedReasons.length > 0 && (
        <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-amber-300">Por qué no entra</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {blockedReasons.slice(0, 6).map((reason) => <span key={reason} className="rounded-full border border-amber-300/20 px-3 py-1 text-xs text-amber-100">{reason}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}

function EquityPanel({ performance }: { performance: Performance | null }) {
  const curve = performance?.equity_curve ?? [];
  const values = curve.map((point) => point.equity);
  const monthly = performance?.monthly_stats ?? [];
  return (
    <div className="premium-card p-5">
      <div className="panel-head"><h2>Curva de equity</h2><span>{curve.length} cierres</span></div>
      <div className="h-32 rounded-2xl border border-cyan-400/10 bg-black/25 p-4">
        {values.length > 1 ? (
          <MiniSparkline values={values} tone={(values.at(-1) ?? 0) >= 0 ? 'green' : 'red'} />
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              <p className="text-sm font-semibold text-slate-300">Sin curva todavía</p>
              <p className="mt-1 text-xs text-slate-500">Aparecerá cuando cierre la primera operación paper.</p>
            </div>
          </div>
        )}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-cyan-400/10 bg-black/25 p-3"><p className="panel-label">Relación wins/losses</p><p className="mt-2 text-xl font-semibold text-cyan-200">{performance?.wins && performance?.losses ? (performance.wins / Math.max(performance.losses, 1)).toFixed(2) : '—'}</p></div>
        <div className="rounded-2xl border border-cyan-400/10 bg-black/25 p-3"><p className="panel-label">Drawdown</p><p className="mt-2 text-xl font-semibold text-rose-300">{performance?.max_drawdown ?? 0}%</p></div>
        <div className="rounded-2xl border border-cyan-400/10 bg-black/25 p-3"><p className="panel-label">Promedio</p><p className="mt-2 text-xl font-semibold text-emerald-300">{performance?.average_return ?? 0}%</p></div>
      </div>
      <div className="mt-4 space-y-2">
        {monthly.slice(0, 3).map((row) => (
          <div key={row.month} className="grid grid-cols-4 gap-2 rounded-xl border border-cyan-400/10 bg-black/20 p-2 text-xs">
            <span className="text-slate-400">{row.month}</span>
            <span>{row.trades} trades</span>
            <span className="text-emerald-300">{row.win_rate}% WR</span>
            <span className={row.pnl_pct >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{formatPct(row.pnl_pct)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function BackendEventsPanel({ aiLogs, selectedCrypto }: { aiLogs?: AiLog[] | null; selectedCrypto: string }) {
  const [expanded, setExpanded] = useState(false);
  const logs = (aiLogs ?? []).filter((log) => logMatchesCrypto(log, selectedCrypto));
  const latestLog = logs[0];
  const visibleLogs = expanded ? logs.slice(0, 8) : logs.slice(0, 1);

  return (
    <div className="premium-card p-5">
      <div className="panel-head"><h2>Eventos del backend</h2><span>{selectedCrypto} · {logs.length} logs</span></div>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="mb-4 w-full rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-left transition hover:border-cyan-300/50 hover:bg-cyan-400/15"
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Último evento</p>
            <p className="mt-2 line-clamp-2 text-sm font-semibold text-white">
              {latestLog?.message ?? 'Esperando eventos del backend y decisiones del bot.'}
            </p>
            {latestLog && <p className="mt-1 text-xs text-slate-500">{formatNewYorkTime(latestLog.timestamp ?? latestLog.time)} · {latestLog.severity ?? 'BACKEND'}</p>}
          </div>
          <div className="shrink-0 text-right">
            <span className="rounded-full bg-cyan-400/15 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-300">
              {expanded ? 'ocultar' : 'ver logs'}
            </span>
          </div>
        </div>
      </button>
      <div className="space-y-3">
        {visibleLogs.map((log, index) => (
          <div key={`${log.timestamp ?? log.time}-${index}`} className="ai-bubble">
            <p className="text-xs text-cyan-300">{formatNewYorkTime(log.timestamp ?? log.time)} · {log.severity ?? 'BACKEND'}</p>
            <p className="mt-1 line-clamp-3 text-sm text-slate-200">{log.message}</p>
            {expanded && log.detail && <p className="mt-1 line-clamp-6 text-xs text-slate-500">{log.detail}</p>}
            {log.condition_snapshot && <p className="mt-2 inline-flex rounded-full border border-cyan-400/20 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-cyan-300">Snapshot estrategia recibido</p>}
          </div>
        ))}
        {logs.length === 0 && <div className="ai-bubble"><p className="text-sm text-slate-300">Esperando eventos del backend y decisiones del bot.</p></div>}
        {!expanded && logs.length > 1 && <p className="text-xs text-slate-500">Hay {logs.length - 1} eventos más ocultos. Toca el resumen para verlos.</p>}
      </div>
    </div>
  );
}

export default function PremiumDashboard() {
  const [timeframe, setTimeframe] = useState('1H');
  const [selectedCrypto, setSelectedCrypto] = useState('BTC');
  const [botControl, setBotControl] = useState<BotControl | null>(null);
  const [botActionBusy, setBotActionBusy] = useState(false);
  const [botActionMessage, setBotActionMessage] = useState('');
  const [closeActionBusy, setCloseActionBusy] = useState(false);
  const [closeActionMessage, setCloseActionMessage] = useState('');
  const [stopLossDraft, setStopLossDraft] = useState('');
  const [stopLossActionBusy, setStopLossActionBusy] = useState(false);
  const [stopLossActionMessage, setStopLossActionMessage] = useState('');
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [paperPanelOpen, setPaperPanelOpen] = useState(false);
  const [summaryPanelOpen, setSummaryPanelOpen] = useState(false);
  const [marketPanelOpen, setMarketPanelOpen] = useState(false);
  const [riskPanelOpen, setRiskPanelOpen] = useState(false);
  const liveNow = useLiveClock();
  const { data: live } = usePolling<LiveMarket>(useCallback(() => fetchLiveMarket(timeframe, selectedCrypto), [timeframe, selectedCrypto]), 3500);
  const { data: snapshots } = usePolling<MarketSnapshot[]>(useCallback(() => fetchMarketSnapshots(), []), 4500);
  const { data: signals } = usePolling<Signal[]>(useCallback(() => fetchSignals(), []), 4000);
  const { data: trades } = usePolling<Trade[]>(useCallback(() => fetchTrades(), []), 5000);
  const { data: performance } = usePolling<Performance>(useCallback(() => fetchPerformance(), []), 6000);
  const { data: aiStatus } = usePolling<AiStatus>(useCallback(() => fetchAiStatus(), []), 5000);
  const { data: aiLogs } = usePolling<AiLog[]>(useCallback(() => fetchAiLogs(), []), 4500);
  const { data: polledBotControl } = usePolling<BotControl>(useCallback(() => fetchBotControl(), []), 3000);
  const { data: userPaperRuntime } = usePolling<UserPaperRuntime>(useCallback(() => fetchUserPaperRuntime(), []), 3500);

  useEffect(() => {
    if (polledBotControl) {
      setBotControl(polledBotControl);
    }
  }, [polledBotControl]);

  const runBotAction = useCallback(async (action: 'start' | 'stop') => {
    setBotActionBusy(true);
    setBotActionMessage(action === 'start' ? 'Activando bot...' : 'Pausando nuevas operaciones...');
    try {
      const next = action === 'start' ? await startBot() : await stopBot();
      setBotControl(next);
      setBotActionMessage(next.active ? 'Bot activo en modo papel.' : 'Bot pausado: no abrirá nuevas operaciones.');
    } catch {
      setBotActionMessage('No se pudo actualizar el bot. Revisa backend.');
    } finally {
      setBotActionBusy(false);
    }
  }, []);

  const runClosePosition = useCallback(async (symbol: string) => {
    setCloseActionBusy(true);
    setCloseActionMessage(`Solicitando cierre de ${symbol}...`);
    try {
      const response = await closePosition(symbol);
      setCloseActionMessage(response.message || `Cierre manual solicitado para ${symbol}.`);
    } catch {
      setCloseActionMessage('No se pudo solicitar el cierre manual. Revisa backend.');
    } finally {
      setCloseActionBusy(false);
    }
  }, []);

  const runStopLossUpdate = useCallback(async (symbol: string, stopLoss: number) => {
    if (!Number.isFinite(stopLoss) || stopLoss <= 0) {
      setStopLossActionMessage('Stop loss inválido.');
      return;
    }
    setStopLossActionBusy(true);
    setStopLossActionMessage(`Solicitando nuevo SL ${formatMoney(stopLoss)}...`);
    try {
      const response = await updateStopLoss(symbol, stopLoss);
      setStopLossActionMessage(response.message || `Stop loss solicitado para ${symbol}.`);
    } catch {
      setStopLossActionMessage('No se pudo actualizar el stop loss. Revisa backend.');
    } finally {
      setStopLossActionBusy(false);
    }
  }, []);

  const snapshot = latestForCrypto(snapshots, selectedCrypto) ?? null;
  const activeSignal = latestForCrypto(signals, selectedCrypto) ?? null;
  const recentTrades = (trades ?? [])
    .filter((trade) => !trade.symbol || matchesCrypto(trade.symbol, selectedCrypto))
    .slice(0, 5);
  const signalHistory = (signals ?? [])
    .filter((item) => matchesCrypto(item.symbol, selectedCrypto))
    .filter((item) => item.id !== activeSignal?.id)
    .slice(0, 4);
  const price = live?.price ?? snapshot?.price ?? 0;
  const selectedMarket = cryptoMarkets.find((market) => market.symbol === selectedCrypto) ?? cryptoMarkets[0];
  const support = live?.support ?? snapshot?.support ?? undefined;
  const resistance = live?.resistance ?? snapshot?.resistance ?? undefined;
  const signal = live?.signal ?? activeSignal?.direction ?? 'WAIT';
  const confidence = live?.confidence ?? activeSignal?.confidence_score ?? aiStatus?.confidence ?? 0;
  const hasTradeSignal = ['LONG', 'SHORT'].includes(String(signal).toUpperCase());
  const risk = activeSignal?.risk_level ?? aiStatus?.risk_level ?? 'Unknown';
  const cumulativePnlPct = performance?.equity_curve?.length
    ? performance.equity_curve[performance.equity_curve.length - 1].equity
    : recentTrades.reduce((sum, trade) => sum + (trade.result_pct ?? 0), 0);
  const closedPaperEquity = paperStartingBalance * (1 + cumulativePnlPct / 100);
  const botActive = botControl?.active ?? true;
  const decisionSnapshot = useMemo(() => parseDecisionSnapshot(aiLogs, selectedCrypto), [aiLogs, selectedCrypto]);
  const paperAccountSnapshot = useMemo(() => parsePaperAccountSnapshot(aiLogs), [aiLogs]);
  const openPositionSnapshot = useMemo(() => parseOpenPositionSnapshot(aiLogs, selectedCrypto), [aiLogs, selectedCrypto]);
  const runtimeOpenPositions = userPaperRuntime?.open_positions ?? [];
  const runtimeSelectedPosition = runtimeOpenPositions.find((position) => matchesCrypto(position.symbol, selectedCrypto));
  const runtimeOpenPositionRaw = runtimeSelectedPosition ? runtimePositionToSnapshot(runtimeSelectedPosition) : null;
  const openPositionRaw = runtimeOpenPositionRaw ?? (openPositionSnapshot?.open_position?.status === 'OPEN' ? openPositionSnapshot.open_position : null);
  const allOpenPositions = useMemo(
    () => runtimeOpenPositions.length
      ? runtimeOpenPositions.map(runtimePositionToSnapshot)
      : paperAccountSnapshot?.open_positions?.filter((position) => position.status === 'OPEN') ?? [],
    [paperAccountSnapshot, runtimeOpenPositions],
  );
  const openPositionSymbol = openPositionRaw?.symbol;
  const { data: openPositionLive } = usePolling<LiveMarket | null>(
    useCallback(() => {
      if (!openPositionSymbol || matchesCrypto(openPositionSymbol, selectedCrypto)) {
        return Promise.resolve(live);
      }
      return fetchLiveMarket(timeframe, openPositionSymbol);
    }, [live, openPositionSymbol, selectedCrypto, timeframe]),
    3500,
  );
  const openPositionMarkPrice = openPositionRaw
    ? matchesCrypto(openPositionRaw.symbol, selectedCrypto)
      ? price
      : openPositionLive?.price ?? openPositionRaw.mark_price ?? 0
    : 0;
  const openPositionIsStale = runtimeOpenPositionRaw ? false : positionExitAlreadyCrossed(openPositionRaw, openPositionMarkPrice);
  const openPosition = openPositionIsStale ? null : openPositionRaw;
  const openPositionNotional = openPosition?.position_usd ?? 0;
  const openPositionLeverage = openPosition?.leverage && openPosition.leverage > 0 ? openPosition.leverage : 1;
  const marginReserved = openPosition ? openPositionNotional / openPositionLeverage : 0;
  const floatingPnl = openPosition?.entry_price && openPositionMarkPrice && openPosition?.position_size
    ? String(openPosition.side).toUpperCase() === 'SHORT'
      ? (openPosition.entry_price - openPositionMarkPrice) * openPosition.position_size
      : (openPositionMarkPrice - openPosition.entry_price) * openPosition.position_size
    : 0;
  const floatingPnlPct = marginReserved ? (floatingPnl / marginReserved) * 100 : 0;
  const accountStartingBalance = userPaperRuntime?.account.starting_balance ?? paperAccountSnapshot?.paper_starting_balance ?? paperStartingBalance;
  const accountClosedBalance = userPaperRuntime?.account.cash_balance ?? paperAccountSnapshot?.paper_balance ?? closedPaperEquity;
  const accountFloatingPnl = openPositionIsStale ? 0 : userPaperRuntime?.account.unrealized_pnl ?? paperAccountSnapshot?.unrealized_pnl ?? floatingPnl;
  const accountPaperEquity = openPositionIsStale ? accountClosedBalance : userPaperRuntime?.account.equity ?? paperAccountSnapshot?.paper_equity ?? (closedPaperEquity + floatingPnl);
  const accountMarginReserved = openPositionIsStale ? 0 : userPaperRuntime?.account.margin_reserved ?? paperAccountSnapshot?.margin_reserved ?? marginReserved;
  const accountOpenNotional = openPositionIsStale ? 0 : userPaperRuntime?.account.open_notional ?? paperAccountSnapshot?.open_notional ?? openPositionNotional;
  const accountAvailableBalance = openPositionIsStale ? accountClosedBalance : userPaperRuntime?.account.cash_balance ?? paperAccountSnapshot?.available_balance ?? Math.max(closedPaperEquity - marginReserved, 0);
  const openPositionsCount = userPaperRuntime?.open_positions_count ?? (
    openPositionIsStale
      ? allOpenPositions.filter((position) => !matchesCrypto(position.symbol, selectedCrypto)).length
      : allOpenPositions.length
  );
  const totalPaperPnlPct = ((accountPaperEquity / accountStartingBalance) - 1) * 100;
  const realizedPaperPnlPct = ((accountClosedBalance / accountStartingBalance) - 1) * 100;
  const riskAtStop = openPosition?.entry_price && openPosition?.stop_loss && openPosition?.position_size
    ? Math.abs(openPosition.entry_price - openPosition.stop_loss) * openPosition.position_size
    : 0;
  const liveCandles = useMemo(() => live?.candles?.map((candle) => ({
    time: candle.time,
    open: Number(candle.open),
    high: Number(candle.high),
    low: Number(candle.low),
    close: Number(candle.close),
    volume: Number(candle.volume),
  })) ?? [], [live?.candles]);
  const liveTelemetry = {
    atr: decisionSnapshot?.atr ?? live?.atr,
    adx: decisionSnapshot?.adx ?? live?.adx,
    volumeRatio: decisionSnapshot?.volume_ratio ?? live?.volume_ratio,
    volume: live?.volume,
    volatilityRatio: decisionSnapshot?.volatility_ratio,
  };
  const hasStrategySnapshot = Boolean(decisionSnapshot?.strategy_checks?.length);
  const strategyChecks = hasStrategySnapshot ? decisionSnapshot?.strategy_checks ?? [] : fallbackStrategyChecks({ live: live ?? null, snapshot, signal, confidence });
  const blockedReasons = decisionSnapshot?.blocked_reasons ?? [];
  const hmmInfo = hmmContext(decisionSnapshot);
  const signalExplanation = activeSignal?.explanation
    || (blockedReasons.length ? `WAIT: ${blockedReasons.slice(0, 3).join(', ')}` : 'Esperando el próximo análisis del bot.');

  useEffect(() => {
    if (openPosition?.stop_loss) {
      setStopLossDraft(String(Number(openPosition.stop_loss).toFixed(2)));
      setStopLossActionMessage('');
    }
  }, [openPosition?.symbol, openPosition?.stop_loss]);

  return (
    <main className="relative min-h-screen overflow-hidden bg-background text-slate-100">
      <div className="ambient-bg" />
      <div className="energy-line energy-line-a" />
      <div className="energy-line energy-line-b" />
      <div className="relative z-10 flex gap-4 p-3 sm:p-4">
        <Sidebar botActive={botActive} liveNow={liveNow} selectedCrypto={selectedCrypto} onCryptoChange={setSelectedCrypto} />
        <section className="min-w-0 flex-1 space-y-4">
          <header className="xl:hidden">
            <div className="premium-card flex flex-col gap-4 p-4 xl:hidden">
              <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-2xl font-bold text-white">LESLY</p>
                <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">NY live · {formatNewYorkTime(liveNow)}</p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-xs ${botActive ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-rose-400/30 bg-rose-400/10 text-rose-300'}`}>
                {botActive ? 'Activo' : 'Pausado'}
              </span>
              </div>
              <CryptoSelector selectedCrypto={selectedCrypto} onChange={setSelectedCrypto} />
            </div>
          </header>

          <section className="grid gap-3 xl:grid-cols-[1fr_0.42fr]">
            <div className="premium-card p-5">
              <div className="panel-head">
                <h2>Resumen principal</h2>
                <button
                  type="button"
                  onClick={() => setSummaryPanelOpen((value) => !value)}
                  className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200 transition hover:border-cyan-200 hover:bg-cyan-300/20"
                >
                  {summaryPanelOpen ? 'ocultar' : 'ver todo'}
                </button>
              </div>
              <button
                type="button"
                onClick={() => setSummaryPanelOpen((value) => !value)}
                className="relative mt-4 grid w-full gap-3 rounded-3xl border border-cyan-400/10 bg-black/25 p-4 pr-28 text-left transition hover:border-cyan-300/30 hover:bg-cyan-300/5 sm:grid-cols-4"
              >
                <span className="absolute right-4 top-1/2 flex h-20 w-20 -translate-y-1/2 flex-col items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10 shadow-[0_0_28px_rgba(34,211,238,0.14)]">
                  <span className="text-[9px] uppercase tracking-[0.16em] text-cyan-200">Abiertas</span>
                  <span className="mt-1 text-3xl font-black leading-none text-white">{openPositionsCount}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Disponible</span>
                  <span className="mt-1 block text-xl font-semibold text-white">{formatMoney(accountAvailableBalance)}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Equity</span>
                  <span className={`mt-1 block text-xl font-semibold ${totalPaperPnlPct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{formatMoney(accountPaperEquity)}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">P&L</span>
                  <span className={`mt-1 block text-xl font-semibold ${totalPaperPnlPct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{formatPct(totalPaperPnlPct)}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Señal</span>
                  <span className={`mt-1 block text-xl font-semibold ${signalTone(signal)}`}>{signal}</span>
                </span>
              </button>
              {summaryPanelOpen && (
                <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <MetricCard label="Balance disponible" value={formatMoney(accountAvailableBalance)} sub={allOpenPositions.length ? `Reservado ${formatMoney(accountMarginReserved)}` : 'sin margen reservado'} tone={accountAvailableBalance >= accountStartingBalance * 0.5 ? 'green' : 'red'} indicatorLabel="Capital" indicatorValue={formatMoney(accountClosedBalance)} />
                  <MetricCard label="Equity papel" value={formatMoney(accountPaperEquity)} sub={formatPct(totalPaperPnlPct)} tone={totalPaperPnlPct >= 0 ? 'green' : 'red'} indicatorLabel="Base" indicatorValue={formatMoney(accountStartingBalance)} />
                  <MetricCard label="P&L papel" value={formatPct(totalPaperPnlPct)} sub={allOpenPositions.length ? `Flotante ${formatMoney(accountFloatingPnl)}` : 'solo trades cerrados'} tone={totalPaperPnlPct >= 0 ? 'green' : 'red'} indicatorLabel="Trades" indicatorValue={String(performance?.total_trades ?? 0)} />
                  <MetricCard label="Riesgo actual" value={String(risk).toUpperCase()} sub={`Confianza ${confidence}%`} tone={String(risk).toLowerCase().includes('high') ? 'red' : 'green'} indicatorLabel="Señal" indicatorValue={signal} />
                </div>
              )}
            </div>
            <div className="premium-card space-y-2 p-4">
              <ControlButtons botActive={botActive} busy={botActionBusy} onStart={() => runBotAction('start')} onStop={() => runBotAction('stop')} />
              <p className={`px-2 text-xs ${botActive ? 'text-emerald-300' : 'text-rose-300'}`}>
                {botActionMessage || (botActive ? 'Bot activo: puede abrir operaciones paper.' : 'Bot pausado: no abrirá nuevas operaciones.')} · NY {formatNewYorkTime(liveNow)}
              </p>
            </div>
          </section>

          <section id="dashboard" className="grid gap-4 xl:grid-cols-[1.55fr_0.72fr_0.62fr]">
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <div className="flex flex-wrap gap-2">
                  {timeframes.map((item) => (
                    <button key={item.value} onClick={() => setTimeframe(item.value)} className={`rounded-xl border px-4 py-2 text-sm transition ${item.value === timeframe ? 'border-blue-400 bg-blue-500/25 text-white shadow-[0_0_24px_rgba(37,99,235,0.45)]' : 'border-cyan-400/10 bg-white/[0.03] text-slate-400 hover:border-cyan-300/40 hover:text-cyan-200'}`} type="button">
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
              <CandleChart
                price={price}
                support={support}
                resistance={resistance}
                timeframe={timeframe}
                candles={liveCandles}
                exchange={live?.exchange}
                label={live?.symbol ?? selectedMarket.display}
                assetName={live?.asset_name ?? selectedMarket.name}
                adx={live?.adx}
                atr={live?.atr}
                volumeRatio={live?.volume_ratio}
              />
            </div>

            <div className="premium-card p-5">
              <div className="panel-head">
                <h2>Snapshot de mercado</h2>
                <button
                  type="button"
                  onClick={() => setMarketPanelOpen((value) => !value)}
                  className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200 transition hover:border-cyan-200 hover:bg-cyan-300/20"
                >
                  {marketPanelOpen ? 'ocultar' : formatNewYorkTime(live?.updated_at ?? snapshot?.updated_at)}
                </button>
              </div>
              <button
                type="button"
                onClick={() => setMarketPanelOpen((value) => !value)}
                className="mt-4 grid w-full gap-3 rounded-3xl border border-cyan-400/10 bg-black/25 p-4 text-left transition hover:border-cyan-300/30 hover:bg-cyan-300/5"
              >
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Precio {live?.asset ?? selectedCrypto}</span>
                  <span className="mt-1 block text-2xl font-semibold text-emerald-300">{formatMoney(price)}</span>
                </span>
                <span className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-slate-400">Cambio 1H</span>
                  <strong className={(live?.change_1h_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{formatPct(live?.change_1h_pct)}</strong>
                </span>
                <span className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-slate-400">Tendencia</span>
                  <strong className="text-emerald-300">{live?.trend ?? snapshot?.trend ?? 'neutral'}</strong>
                </span>
              </button>
              {marketPanelOpen && (
                <div className="mt-4 divide-y divide-cyan-400/10">
                  {[
                    [`Precio ${live?.asset ?? selectedCrypto}`, formatMoney(price), 'text-emerald-300'],
                    ['Cambio 1H', formatPct(live?.change_1h_pct), (live?.change_1h_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'],
                    ['Soporte', formatMoney(support), 'text-cyan-300'],
                    ['Resistencia', formatMoney(resistance), 'text-rose-300'],
                    ['Tendencia', live?.trend ?? snapshot?.trend ?? 'neutral', 'text-emerald-300'],
                    ['Exchange', live?.exchange ? live.exchange.toUpperCase() : 'fallback', 'text-cyan-300'],
                  ].map(([label, value, className]) => (
                    <div key={label} className="flex items-center justify-between py-4 text-sm"><span className="text-slate-400">{label}</span><strong className={className}>{value}</strong></div>
                  ))}
                </div>
              )}
            </div>

            <SystemStatus aiStatus={aiStatus} />
          </section>

          <section id="riesgo" className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <StrategyMatrix checks={strategyChecks} blockedReasons={blockedReasons} />
            <div className="premium-card p-5">
              <div className="panel-head">
                <h2>Control de riesgo</h2>
                <button
                  type="button"
                  onClick={() => setRiskPanelOpen((value) => !value)}
                  className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200 transition hover:border-cyan-200 hover:bg-cyan-300/20"
                >
                  {riskPanelOpen ? 'ocultar' : 'paper safe'}
                </button>
              </div>
              <button
                type="button"
                onClick={() => setRiskPanelOpen((value) => !value)}
                className="mt-4 grid w-full gap-3 rounded-3xl border border-cyan-400/10 bg-black/25 p-4 text-left transition hover:border-cyan-300/30 hover:bg-cyan-300/5 sm:grid-cols-3"
              >
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">ADX {timeframe}</span>
                  <span className="mt-1 block text-xl font-semibold text-emerald-300">{liveTelemetry.adx ? number.format(liveTelemetry.adx) : '—'}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Volumen</span>
                  <span className="mt-1 block text-xl font-semibold text-cyan-300">{liveTelemetry.volumeRatio ? `${liveTelemetry.volumeRatio.toFixed(2)}x` : '—'}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">ATR</span>
                  <span className="mt-1 block text-xl font-semibold text-cyan-300">{liveTelemetry.atr ? number.format(liveTelemetry.atr) : '—'}</span>
                </span>
              </button>
              {riskPanelOpen && (
                <div className="mt-4 space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {[
                      ['ATR real', liveTelemetry.atr ? number.format(liveTelemetry.atr) : 'Esperando exchange', 'text-cyan-300'],
                      [`ADX ${timeframe}`, liveTelemetry.adx ? number.format(liveTelemetry.adx) : 'Esperando exchange', 'text-emerald-300'],
                      ['Volumen', liveTelemetry.volumeRatio ? `${liveTelemetry.volumeRatio.toFixed(2)}x` : 'Esperando exchange', 'text-cyan-300'],
                      ['Volatilidad', liveTelemetry.volatilityRatio ? `${liveTelemetry.volatilityRatio.toFixed(2)} ATR` : liveTelemetry.volume ? number.format(liveTelemetry.volume) : 'Esperando exchange', 'text-amber-300'],
                    ].map(([label, value, className]) => (
                      <div key={label} className="rounded-2xl border border-cyan-400/10 bg-black/25 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
                        <p className={`mt-2 text-2xl font-semibold ${className}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-2xl border border-cyan-400/10 bg-black/25 p-4 text-sm text-slate-300">
                    <p>Entradas solo con vela cerrada, confirmación 1D/4H/1H, ADX y volumen obligatorios.</p>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section id="señales" className="grid gap-4 xl:grid-cols-[0.9fr_1fr_0.82fr]">
            <div className="premium-card p-5">
              <div className="panel-head"><h2>Señal actual</h2><span className={signalTone(signal)}>{signal}</span></div>
              <div className={`rounded-3xl border p-5 ${signalTone(signal)}`}>
                <p className="text-5xl font-black tracking-tight">{signal}</p>
                <p className="mt-4 text-sm text-slate-300">{signalExplanation}</p>
                <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-slate-500">{hasTradeSignal ? 'Entrada estimada' : 'Precio actual'}</span><p className="font-semibold text-white">{formatMoney(price)}</p></div>
                  <div><span className="text-slate-500">Confianza</span><p className="font-semibold text-emerald-300">{confidence}%</p></div>
                  <div><span className="text-slate-500">{hasTradeSignal ? 'Referencia soporte' : 'Soporte'}</span><p className="font-semibold text-cyan-300">{formatMoney(support)}</p></div>
                  <div><span className="text-slate-500">{hasTradeSignal ? 'Referencia resistencia' : 'Resistencia'}</span><p className="font-semibold text-rose-300">{formatMoney(resistance)}</p></div>
                </div>
              </div>
              {openPosition && (
                <div className={`mt-4 rounded-3xl border p-5 ${signalTone(openPosition.side)}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Operación live</p>
                      <p className="mt-2 text-3xl font-black">{openPosition.symbol} {openPosition.side}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-emerald-300">open</span>
                      <button
                        type="button"
                        disabled={closeActionBusy}
                        onClick={() => runClosePosition(openPosition.symbol ?? selectedCrypto)}
                        className="rounded-full border border-cyan-300/40 bg-cyan-300/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.16)] transition hover:border-cyan-200 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Tomar TP
                      </button>
                    </div>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                    <div><span className="text-slate-500">Temporalidad</span><p className="font-semibold text-white">{openPosition.entry_timeframe ?? '—'}</p></div>
                    <div><span className="text-slate-500">Apalancamiento</span><p className="font-semibold text-cyan-300">{openPosition.leverage ? `${openPosition.leverage.toFixed(2)}x` : '—'}</p></div>
                    <div><span className="text-slate-500">Entrada</span><p className="font-semibold text-white">{formatMoney(openPosition.entry_price)}</p></div>
                    <div><span className="text-slate-500">Precio actual</span><p className="font-semibold text-white">{formatMoney(openPositionMarkPrice)}</p></div>
                    <div><span className="text-slate-500">Contrato</span><p className="font-semibold text-white">{formatMoney(openPosition.position_usd)}</p></div>
                    <div><span className="text-slate-500">PnL flotante</span><p className={`font-semibold ${floatingPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{formatMoney(floatingPnl)} · {formatPct(floatingPnlPct)}</p></div>
                    <div><span className="text-slate-500">Stop loss</span><p className="font-semibold text-rose-300">{formatMoney(openPosition.stop_loss)}</p></div>
                    <div><span className="text-slate-500">Take profit</span><p className="font-semibold text-cyan-300">{formatMoney(openPosition.take_profit)}</p></div>
                  </div>
                  {closeActionMessage && <p className="mt-3 text-xs text-cyan-200">{closeActionMessage}</p>}
                  <div className="mt-4 rounded-2xl border border-cyan-400/10 bg-black/25 p-4">
                    <div className="flex flex-wrap items-end gap-3">
                      <label className="min-w-[150px] flex-1">
                        <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Mover stop loss</span>
                        <input
                          type="number"
                          inputMode="decimal"
                          step="0.01"
                          value={stopLossDraft}
                          onChange={(event) => setStopLossDraft(event.target.value)}
                          className="mt-2 w-full rounded-xl border border-cyan-400/20 bg-black/35 px-3 py-2 text-sm font-semibold text-white outline-none transition focus:border-cyan-300"
                        />
                      </label>
                      <button
                        type="button"
                        disabled={stopLossActionBusy}
                        onClick={() => {
                          const entry = Number(openPosition.entry_price ?? 0);
                          setStopLossDraft(entry ? entry.toFixed(2) : '');
                          if (entry) runStopLossUpdate(openPosition.symbol ?? selectedCrypto, entry);
                        }}
                        className="rounded-xl border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-200 transition hover:border-emerald-200 hover:bg-emerald-300/20 disabled:opacity-50"
                      >
                        SL entrada
                      </button>
                      <button
                        type="button"
                        disabled={stopLossActionBusy}
                        onClick={() => runStopLossUpdate(openPosition.symbol ?? selectedCrypto, Number(stopLossDraft))}
                        className="rounded-xl border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-cyan-100 transition hover:border-cyan-200 hover:bg-cyan-300/20 disabled:opacity-50"
                      >
                        Guardar SL
                      </button>
                    </div>
                    {stopLossActionMessage && <p className="mt-3 text-xs text-cyan-200">{stopLossActionMessage}</p>}
                  </div>
                  <p className="mt-4 text-xs text-slate-500">Abierta NY {formatNewYorkDateTime(openPosition.opened_at)}</p>
                </div>
              )}
            </div>

            <div className="premium-card p-5">
              <div className="panel-head">
                <h2>Paper trading</h2>
                <button
                  type="button"
                  onClick={() => setPaperPanelOpen((value) => !value)}
                  className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200 transition hover:border-cyan-200 hover:bg-cyan-300/20"
                >
                  {paperPanelOpen ? 'ocultar' : 'ver stats'}
                </button>
              </div>
              <button
                type="button"
                onClick={() => setPaperPanelOpen((value) => !value)}
                className="mt-4 grid w-full gap-3 rounded-3xl border border-cyan-400/10 bg-black/25 p-4 text-left transition hover:border-cyan-300/30 hover:bg-cyan-300/5 sm:grid-cols-3"
              >
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Equity</span>
                  <span className={`mt-1 block text-xl font-semibold ${totalPaperPnlPct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{formatMoney(accountPaperEquity)}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Disponible</span>
                  <span className="mt-1 block text-xl font-semibold text-emerald-300">{formatMoney(accountAvailableBalance)}</span>
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">P&L papel</span>
                  <span className={`mt-1 block text-xl font-semibold ${totalPaperPnlPct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{formatPct(totalPaperPnlPct)}</span>
                </span>
              </button>
              {paperPanelOpen && (
                <div className="mt-5 space-y-5">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {[
                      ['Capital papel', formatMoney(accountClosedBalance), 'text-white'],
                      ['Equity actual', formatMoney(accountPaperEquity), totalPaperPnlPct >= 0 ? 'text-emerald-300' : 'text-rose-300'],
                      ['Disponible', formatMoney(accountAvailableBalance), 'text-emerald-300'],
                      ['Margen reservado', formatMoney(accountMarginReserved), allOpenPositions.length ? 'text-amber-300' : 'text-slate-500'],
                      ['Contrato abierto', formatMoney(accountOpenNotional), allOpenPositions.length ? 'text-cyan-300' : 'text-slate-500'],
                      ['PnL flotante', `${formatMoney(accountFloatingPnl)} · ${formatPct(totalPaperPnlPct)}`, accountFloatingPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'],
                      ['PnL realizado', formatPct(realizedPaperPnlPct), realizedPaperPnlPct >= 0 ? 'text-emerald-300' : 'text-rose-300'],
                      ['Precio posición', formatMoney(openPositionMarkPrice), openPosition ? 'text-white' : 'text-slate-500'],
                      ['Riesgo hasta SL', formatMoney(riskAtStop), openPosition ? 'text-rose-300' : 'text-slate-500'],
                      ['Posición', openPosition ? `${openPosition.symbol} ${openPosition.side}` : 'Sin posición abierta', openPosition?.side === 'SHORT' ? 'text-rose-300' : openPosition?.side === 'LONG' ? 'text-emerald-300' : 'text-slate-500'],
                    ].map(([label, value, className]) => (
                      <div key={label} className="rounded-2xl border border-cyan-400/10 bg-black/25 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
                        <p className={`mt-2 text-xl font-semibold ${className}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    {[
                      ['Win rate', `${performance?.win_rate ?? 0}%`, 'text-emerald-300'],
                      ['Ganados', String(performance?.wins ?? 0), 'text-emerald-300'],
                      ['Perdidos', String(performance?.losses ?? 0), 'text-rose-300'],
                      ['Trades', String(performance?.total_trades ?? 0), 'text-white'],
                      ['Drawdown', `${performance?.max_drawdown ?? 0}%`, 'text-rose-300'],
                      ['Avg return', `${performance?.average_return ?? 0}%`, 'text-cyan-300'],
                    ].map(([label, value, className]) => <div key={label} className="rounded-2xl border border-cyan-400/10 bg-black/25 p-4"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p><p className={`mt-2 text-2xl font-semibold ${className}`}>{value}</p></div>)}
                  </div>
                  <div className="h-32 rounded-2xl border border-cyan-400/10 bg-black/25 p-4">
                    {performance?.equity_curve?.length && performance.equity_curve.length > 1 ? (
                      <MiniSparkline values={performance.equity_curve.map((point) => point.equity)} tone="green" />
                    ) : (
                      <div className="grid h-full place-items-center text-center">
                        <div>
                          <p className="text-sm font-semibold text-slate-300">Esperando trades cerrados</p>
                          <p className="mt-1 text-xs text-slate-500">Aquí irá la curva real del paper trading.</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="premium-card p-5">
              <div className="panel-head"><h2>Historial de señales</h2><span>{signalHistory.length}</span></div>
              <div className="space-y-3">
                {signalHistory.length === 0 && <p className="text-sm text-slate-500">Sin señales históricas para {selectedCrypto} todavía.</p>}
                {signalHistory.map((item) => <div key={item.id} className="flex items-center justify-between rounded-2xl border border-cyan-400/10 bg-black/25 p-3 text-sm"><span className={item.direction === 'SHORT' ? 'text-rose-300' : item.direction === 'LONG' ? 'text-emerald-300' : 'text-cyan-300'}>{item.direction}</span><span className="text-slate-400">{item.confidence_score}%</span><span className="text-slate-500">{formatNewYorkDateTime(item.created_at)}</span></div>)}
              </div>
            </div>
          </section>

          <section id="backtesting" className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <EquityPanel performance={performance} />
            <div className="premium-card p-5">
              <div className="panel-head"><h2>Trade journal</h2><span>{recentTrades.length} recientes</span></div>
              <div className="space-y-3">
                {recentTrades.length === 0 && <p className="text-sm text-slate-500">El journal se llenará cuando cierren operaciones paper.</p>}
                {recentTrades.map((trade) => (
                  <div key={`journal-${trade.id}`} className="rounded-2xl border border-cyan-400/10 bg-black/25 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span className="font-semibold text-white">Trade #{trade.id}</span>
                      <span className="text-slate-500">{formatNewYorkDateTime(trade.closed_at ?? trade.opened_at)}</span>
                      <span className={(trade.result_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{formatPct(trade.result_pct)}</span>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs sm:grid-cols-4">
                      <span className="text-slate-400">Entrada {formatMoney(trade.entry_price)}</span>
                      <span className="text-rose-300">SL {formatMoney(trade.stop_loss)}</span>
                      <span className="text-cyan-300">TP {formatMoney(trade.take_profit)}</span>
                      <span className="text-slate-400">Cierre {formatMoney(trade.closed_price)}</span>
                    </div>
                    {trade.notes && <p className="mt-2 line-clamp-2 text-xs text-slate-500">{trade.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section id="ia-chat" className="grid gap-4 xl:grid-cols-[0.82fr_1fr_0.82fr]">
            <div className="premium-card p-5">
              <div className="panel-head">
                <h2>IA análisis</h2>
                <button
                  type="button"
                  onClick={() => setAiPanelOpen((value) => !value)}
                  className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200 transition hover:border-cyan-200 hover:bg-cyan-300/20"
                >
                  {aiPanelOpen ? 'ocultar' : aiStatus?.engine_status ?? 'online'}
                </button>
              </div>
              {aiPanelOpen ? (
                <div className="space-y-4">
                  {[
                    ['Señal', signal],
                    ['Tendencia', live?.trend ?? snapshot?.trend ?? 'neutral'],
                    ['Temporalidad dominante', timeframe],
                    ['Momentum', (live?.change_1h_pct ?? 0) >= 0 ? 'positivo' : 'defensivo'],
                    ['Régimen HMM', `${hmmInfo.regime} · ${hmmInfo.status}`],
                    ['Contexto HMM', hmmInfo.label],
                    ['Validación IA', aiStatus?.mode ?? 'paper'],
                    ['Último análisis', formatNewYorkDateTime(aiStatus?.last_analysis_time)],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl border border-cyan-400/10 bg-black/25 p-3"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p><p className="mt-1 font-semibold text-white">{value}</p></div>
                  ))}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setAiPanelOpen(true)}
                  className="mt-4 flex w-full items-center justify-between rounded-2xl border border-cyan-400/10 bg-black/25 p-4 text-left transition hover:border-cyan-300/30 hover:bg-cyan-300/5"
                >
                  <span>
                    <span className="block text-xs uppercase tracking-[0.18em] text-slate-500">Resumen IA</span>
                    <span className="mt-1 block font-semibold text-white">{signal} · {live?.trend ?? snapshot?.trend ?? 'neutral'} · {hmmInfo.label}</span>
                  </span>
                  <span className="text-xs uppercase tracking-[0.18em] text-cyan-200">ver</span>
                </button>
              )}
            </div>
            <BackendEventsPanel aiLogs={aiLogs} selectedCrypto={selectedCrypto} />
            <div className="premium-card p-5">
              <div className="panel-head"><h2>Últimas operaciones</h2><span>{recentTrades.length}</span></div>
              <div className="space-y-3">
                {recentTrades.length === 0 && <p className="text-sm text-slate-500">Sin operaciones cerradas todavía.</p>}
                {recentTrades.map((trade) => <div key={trade.id} className="grid gap-1 rounded-2xl border border-cyan-400/10 bg-black/25 p-3 text-sm sm:grid-cols-[auto_1fr_auto_auto] sm:items-center"><span className="text-slate-300">#{trade.id}</span><span className="text-slate-500 sm:text-center">{formatNewYorkDateTime(trade.closed_at ?? trade.opened_at)}</span><span className="text-slate-300">{formatMoney(trade.entry_price)}</span><span className={(trade.result_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{formatPct(trade.result_pct)}</span></div>)}
              </div>
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
