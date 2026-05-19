import TradingPanel from './TradingPanel';

export default function Hero() {
  return (
    <section className="relative overflow-hidden rounded-[40px] border border-slate-800 bg-surface/90 px-6 py-10 shadow-glow backdrop-blur-xl sm:px-10 lg:px-14">
      <div className="absolute inset-0 bg-neon-grid opacity-30" />
      <div className="relative grid gap-10 lg:grid-cols-[1fr_0.95fr] lg:items-center">
        <div className="space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-glow/30 bg-glow/5 px-4 py-2 text-xs uppercase tracking-[0.3em] text-glow shadow-glow">
            Paper Trading · AI-Driven Signals
          </div>
          <div className="space-y-6">
            <h1 className="max-w-3xl text-5xl font-semibold tracking-tight text-white sm:text-6xl">
              Automated AI Crypto Trading 24/7
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-300">
              Multi-timeframe analysis, intelligent risk management and real-time automated execution.
            </p>
          </div>
          <div className="flex flex-col gap-4 sm:flex-row">
            <button className="inline-flex items-center justify-center rounded-full bg-glow px-7 py-3 text-sm font-semibold text-slate-950 shadow-glow hover:bg-glow/90">
              Launch Dashboard
            </button>
            <button className="inline-flex items-center justify-center rounded-full border border-slate-700 bg-white/5 px-7 py-3 text-sm text-slate-200 hover:border-glow hover:text-white">
              View Live Signals
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-3xl border border-slate-800 bg-[#06101c] p-5 shadow-glow">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-400">BTC Price</p>
              <p className="mt-3 text-3xl font-semibold text-white">$63,498</p>
              <p className="mt-2 text-sm text-slate-400">1.2% ↑ in 1H · Paper Mode</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-[#06101c] p-5 shadow-glow">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-400">AI Status</p>
              <p className="mt-3 text-3xl font-semibold text-glow">Engine Online</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
                <span className="rounded-full bg-slate-900/70 px-3 py-1">LONG Signal</span>
                <span className="rounded-full bg-slate-900/70 px-3 py-1">Paper Trading</span>
                <span className="rounded-full bg-slate-900/70 px-3 py-1">Confidence 87%</span>
              </div>
            </div>
          </div>
        </div>
        <TradingPanel />
      </div>
    </section>
  );
}
