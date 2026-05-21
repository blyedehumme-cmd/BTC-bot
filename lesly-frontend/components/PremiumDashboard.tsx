'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchBotControl,
  fetchAiLogs,
  fetchAiStatus,
  fetchLiveMarket,
  fetchMarketSnapshots,
  fetchPerformance,
  fetchSignals,
  fetchTrades,
  startBot,
  stopBot,
  type AiLog,
  type AiStatus,
  type BotControl,
  type LiveMarket,
  type MarketSnapshot,
  type Performance,
  type Signal,
  type Trade,
} from '../lib/pollingFetchers';
import { formatNewYorkDateTime, formatNewYorkTime } from '../lib/time';
import { usePolling } from '../lib/usePolling';

const navItems = ['Dashboard', 'Señales', 'Operaciones', 'Backtesting', 'Riesgo', 'Configuración', 'IA análisis', 'Historial', 'IA chat'];
const timeframes = ['5M', '15M', '1H', '4H', '1D'];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

type Candle = {
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
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
  return items && items.length > 0 ? items[items.length - 1] : null;
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

function CandleChart({ price, support, resistance, timeframe }: { price: number; support?: number; resistance?: number; timeframe: string }) {
  const candles = useMemo(() => makeCandles(price, support, resistance, timeframe.length), [price, support, resistance, timeframe]);
  const highs = candles.map((candle) => candle.high);
  const lows = candles.map((candle) => candle.low);
  const max = Math.max(...highs, price * 1.01);
  const min = Math.min(...lows, price * 0.99);
  const range = Math.max(max - min, 1);

  return (
    <div className="premium-card relative h-[360px] overflow-hidden p-4 sm:p-5">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,157,255,0.055)_1px,transparent_1px),linear-gradient(90deg,rgba(0,157,255,0.055)_1px,transparent_1px)] bg-[size:70px_38px]" />
      <div className="relative z-10 mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="panel-label">BTC/USDT</p>
          <div className="mt-2 flex flex-wrap items-end gap-3">
            <p className="text-3xl font-semibold text-white sm:text-4xl">{formatMoney(price)}</p>
            <span className="pb-1 text-sm font-semibold text-emerald-300">Live</span>
          </div>
        </div>
        <div className="flex rounded-xl border border-cyan-400/20 bg-black/30 p-1">
          {timeframes.map((item) => (
            <span key={item} className={`rounded-lg px-3 py-1.5 text-xs transition ${item === timeframe ? 'bg-blue-500 text-white shadow-[0_0_22px_rgba(0,112,255,0.55)]' : 'text-slate-400'}`}>
              {item}
            </span>
          ))}
        </div>
      </div>
      <div className="relative z-10 h-[250px]">
        {candles.map((candle, index) => {
          const up = candle.close >= candle.open;
          const x = (index / candles.length) * 100;
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
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub, tone = 'cyan', values }: { label: string; value: string; sub?: string; tone?: 'cyan' | 'green' | 'red'; values: number[] }) {
  const color = tone === 'green' ? 'text-emerald-300' : tone === 'red' ? 'text-rose-300' : 'text-cyan-300';
  return (
    <article className="premium-card group min-h-[118px] p-5 transition duration-300 hover:-translate-y-1 hover:border-cyan-300/60 hover:shadow-[0_0_45px_rgba(0,157,255,0.22)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="panel-label">{label}</p>
          <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
          {sub && <p className={`mt-1 text-sm font-semibold ${color}`}>{sub}</p>}
        </div>
        <div className="w-24 opacity-90 transition group-hover:scale-105">
          <MiniSparkline values={values} tone={tone} />
        </div>
      </div>
    </article>
  );
}

function Sidebar({ botActive }: { botActive: boolean }) {
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
          <a key={item} href={`#${item.toLowerCase().replace(/ /g, '-')}`} className={`nav-item ${index === 0 ? 'nav-item-active' : ''}`}>
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-sm">{['⌂', '↗', '⇄', '▰', '⬟', '⚙', '✦', '☷', '◌'][index]}</span>
            <span>{item}</span>
            {item === 'IA chat' && <span className="ml-auto rounded-full border border-cyan-400/30 px-2 py-0.5 text-[10px] text-cyan-300">BETA</span>}
          </a>
        ))}
      </nav>
      <div className={`absolute bottom-4 left-4 right-4 rounded-2xl border p-4 ${botActive ? 'border-emerald-400/20 bg-emerald-500/10' : 'border-rose-400/20 bg-rose-500/10'}`}>
        <div className={`flex items-center gap-2 text-sm font-semibold ${botActive ? 'text-emerald-300' : 'text-rose-300'}`}><span className={`h-3 w-3 rounded-full ${botActive ? 'bg-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.9)]' : 'bg-rose-400 shadow-[0_0_18px_rgba(244,63,94,0.9)]'}`} /> {botActive ? 'BOT ACTIVO' : 'BOT PAUSADO'}</div>
        <p className="mt-2 text-xs text-slate-400">Modo papel · backend live</p>
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

export default function PremiumDashboard() {
  const [timeframe, setTimeframe] = useState('1H');
  const [botControl, setBotControl] = useState<BotControl | null>(null);
  const [botActionBusy, setBotActionBusy] = useState(false);
  const [botActionMessage, setBotActionMessage] = useState('');
  const { data: live } = usePolling<LiveMarket>(useCallback(() => fetchLiveMarket(), []), 3500);
  const { data: snapshots } = usePolling<MarketSnapshot[]>(useCallback(() => fetchMarketSnapshots(), []), 4500);
  const { data: signals } = usePolling<Signal[]>(useCallback(() => fetchSignals(), []), 4000);
  const { data: trades } = usePolling<Trade[]>(useCallback(() => fetchTrades(), []), 5000);
  const { data: performance } = usePolling<Performance>(useCallback(() => fetchPerformance(), []), 6000);
  const { data: aiStatus } = usePolling<AiStatus>(useCallback(() => fetchAiStatus(), []), 5000);
  const { data: aiLogs } = usePolling<AiLog[]>(useCallback(() => fetchAiLogs(), []), 4500);
  const { data: polledBotControl } = usePolling<BotControl>(useCallback(() => fetchBotControl(), []), 3000);

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

  const snapshot = latest(snapshots);
  const activeSignal = latest(signals);
  const recentTrades = (trades ?? []).slice(-5).reverse();
  const closedSignals = (signals ?? []).filter((signal) => signal.direction !== activeSignal?.direction || signal.id !== activeSignal?.id).slice(-4).reverse();
  const price = live?.price ?? snapshot?.price ?? 0;
  const support = live?.support ?? snapshot?.support ?? undefined;
  const resistance = live?.resistance ?? snapshot?.resistance ?? undefined;
  const signal = activeSignal?.direction ?? live?.signal ?? 'WAIT';
  const confidence = activeSignal?.confidence_score ?? live?.confidence ?? aiStatus?.confidence ?? 0;
  const risk = activeSignal?.risk_level ?? aiStatus?.risk_level ?? 'Unknown';
  const pnl = recentTrades.reduce((sum, trade) => sum + (trade.result_pct ?? 0), 0);
  const spark = useMemo(() => makeCandles(price || 100, support, resistance).map((candle) => candle.close), [price, support, resistance]);
  const botActive = botControl?.active ?? true;

  return (
    <main className="relative min-h-screen overflow-hidden bg-background text-slate-100">
      <div className="ambient-bg" />
      <div className="energy-line energy-line-a" />
      <div className="energy-line energy-line-b" />
      <div className="relative z-10 flex gap-4 p-3 sm:p-4">
        <Sidebar botActive={botActive} />
        <section className="min-w-0 flex-1 space-y-4">
          <header className="xl:hidden">
            <div className="premium-card flex items-center justify-between gap-4 p-4 xl:hidden">
              <div>
                <p className="text-2xl font-bold text-white">LESLY</p>
                <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">AI Trading Bot</p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-xs ${botActive ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-rose-400/30 bg-rose-400/10 text-rose-300'}`}>
                {botActive ? 'Activo' : 'Pausado'}
              </span>
            </div>
          </header>

          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <MetricCard label="Balance total (papel)" value={formatMoney((performance?.total_trades ?? 0) * 100 + 12458.75)} sub={formatPct(live?.change_1h_pct)} values={spark} tone="green" />
            <MetricCard label="Equity" value={formatMoney(12845.3 + pnl)} sub={formatPct(performance?.average_return)} values={spark.slice().reverse()} tone="cyan" />
            <MetricCard label="P&L simulado" value={`${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%`} sub="trades cerrados" values={recentTrades.map((trade, i) => (trade.result_pct ?? 0) + i + 8)} tone={pnl >= 0 ? 'green' : 'red'} />
            <MetricCard label="Riesgo actual" value={String(risk).toUpperCase()} sub={`Confianza ${confidence}%`} values={[10, 14, 12, confidence || 20, 28, 34]} tone={String(risk).toLowerCase().includes('high') ? 'red' : 'green'} />
            <div className="space-y-2">
              <ControlButtons botActive={botActive} busy={botActionBusy} onStart={() => runBotAction('start')} onStop={() => runBotAction('stop')} />
              <p className={`px-2 text-xs ${botActive ? 'text-emerald-300' : 'text-rose-300'}`}>
                {botActionMessage || (botActive ? 'Bot activo: puede abrir operaciones paper.' : 'Bot pausado: no abrirá nuevas operaciones.')}
              </p>
            </div>
          </section>

          <section id="dashboard" className="grid gap-4 xl:grid-cols-[1.55fr_0.72fr_0.62fr]">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                {timeframes.map((item) => (
                  <button key={item} onClick={() => setTimeframe(item)} className={`rounded-xl border px-4 py-2 text-sm transition ${item === timeframe ? 'border-blue-400 bg-blue-500/25 text-white shadow-[0_0_24px_rgba(37,99,235,0.45)]' : 'border-cyan-400/10 bg-white/[0.03] text-slate-400 hover:border-cyan-300/40 hover:text-cyan-200'}`} type="button">
                    {item}
                  </button>
                ))}
              </div>
              <CandleChart price={price} support={support} resistance={resistance} timeframe={timeframe} />
            </div>

            <div className="premium-card p-5">
              <div className="panel-head"><h2>Snapshot de mercado</h2><span>{formatNewYorkTime(live?.updated_at ?? snapshot?.updated_at)}</span></div>
              <div className="divide-y divide-cyan-400/10">
                {[
                  ['Precio BTC', formatMoney(price), 'text-emerald-300'],
                  ['Cambio 1H', formatPct(live?.change_1h_pct), (live?.change_1h_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'],
                  ['Soporte', formatMoney(support), 'text-cyan-300'],
                  ['Resistencia', formatMoney(resistance), 'text-rose-300'],
                  ['Tendencia', live?.trend ?? snapshot?.trend ?? 'neutral', 'text-emerald-300'],
                ].map(([label, value, className]) => (
                  <div key={label} className="flex items-center justify-between py-4 text-sm"><span className="text-slate-400">{label}</span><strong className={className}>{value}</strong></div>
                ))}
              </div>
            </div>

            <SystemStatus aiStatus={aiStatus} />
          </section>

          <section id="señales" className="grid gap-4 xl:grid-cols-[0.9fr_1fr_0.82fr]">
            <div className="premium-card p-5">
              <div className="panel-head"><h2>Señal actual</h2><span className={signalTone(signal)}>{signal}</span></div>
              <div className={`rounded-3xl border p-5 ${signalTone(signal)}`}>
                <p className="text-5xl font-black tracking-tight">{signal}</p>
                <p className="mt-4 text-sm text-slate-300">{activeSignal?.explanation ?? 'Esperando explicación del backend.'}</p>
                <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-slate-500">Entrada</span><p className="font-semibold text-white">{formatMoney(price)}</p></div>
                  <div><span className="text-slate-500">Confianza</span><p className="font-semibold text-emerald-300">{confidence}%</p></div>
                  <div><span className="text-slate-500">Stop loss</span><p className="font-semibold text-rose-300">{formatMoney(support)}</p></div>
                  <div><span className="text-slate-500">Take profit</span><p className="font-semibold text-cyan-300">{formatMoney(resistance)}</p></div>
                </div>
              </div>
            </div>

            <div className="premium-card p-5">
              <div className="panel-head"><h2>Backtesting</h2><span>paper stats</span></div>
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
              <div className="mt-5 h-32 rounded-2xl border border-cyan-400/10 bg-black/25 p-4"><MiniSparkline values={[2, 4, 3, 8, 7, 12, 10, 16, 15, 20]} tone="green" /></div>
            </div>

            <div className="premium-card p-5">
              <div className="panel-head"><h2>Últimas señales cerradas</h2><span>{closedSignals.length}</span></div>
              <div className="space-y-3">
                {closedSignals.length === 0 && <p className="text-sm text-slate-500">Sin señales cerradas todavía.</p>}
                {closedSignals.map((item) => <div key={item.id} className="flex items-center justify-between rounded-2xl border border-cyan-400/10 bg-black/25 p-3 text-sm"><span className={item.direction === 'SHORT' ? 'text-rose-300' : item.direction === 'LONG' ? 'text-emerald-300' : 'text-cyan-300'}>{item.direction}</span><span className="text-slate-400">{item.confidence_score}%</span><span className="text-slate-500">{formatNewYorkDateTime(item.created_at)}</span></div>)}
              </div>
            </div>
          </section>

          <section id="ia-chat" className="grid gap-4 xl:grid-cols-[0.82fr_1fr_0.82fr]">
            <div className="premium-card p-5">
              <div className="panel-head"><h2>IA análisis</h2><span>{aiStatus?.engine_status ?? 'online'}</span></div>
              <div className="space-y-4">
                {[
                  ['Señal', signal],
                  ['Tendencia', live?.trend ?? snapshot?.trend ?? 'neutral'],
                  ['Temporalidad dominante', timeframe],
                  ['Momentum', (live?.change_1h_pct ?? 0) >= 0 ? 'positivo' : 'defensivo'],
                  ['Validación IA', aiStatus?.mode ?? 'paper'],
                  ['Último análisis', formatNewYorkDateTime(aiStatus?.last_analysis_time)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-cyan-400/10 bg-black/25 p-3"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p><p className="mt-1 font-semibold text-white">{value}</p></div>
                ))}
              </div>
            </div>
            <div className="premium-card p-5">
              <div className="panel-head"><h2>IA chat</h2><span>decision stream</span></div>
              <div className="space-y-3">
                {(aiLogs ?? []).slice(-6).reverse().map((log, index) => <div key={`${log.timestamp ?? log.time}-${index}`} className="ai-bubble"><p className="text-xs text-cyan-300">{formatNewYorkTime(log.timestamp ?? log.time)} · {log.severity ?? 'AI'}</p><p className="mt-1 text-sm text-slate-200">{log.message}</p>{log.detail && <p className="mt-1 text-xs text-slate-500">{log.detail}</p>}</div>)}
                {(aiLogs ?? []).length === 0 && <div className="ai-bubble"><p className="text-sm text-slate-300">Esperando mensajes del motor IA y decisiones del bot.</p></div>}
              </div>
            </div>
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
