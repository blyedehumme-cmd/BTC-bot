import Hero from '../components/Hero';
import FeatureCards from '../components/FeatureCards';
import AiLogs from '../components/AiLogs';
import AiStatusPanel from '../components/AiStatusPanel';
import MarketSnapshotPanel from '../components/MarketSnapshotPanel';
import PerformancePanel from '../components/PerformancePanel';
import SignalBoard from '../components/SignalBoard';
import Footer from '../components/Footer';

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
        <header className="mb-12 flex flex-col gap-6 text-white sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-3xl font-semibold tracking-tight">Lesly</p>
            <p className="text-sm text-slate-400">AI Crypto Trading in Paper Mode</p>
          </div>
          <nav className="flex flex-wrap items-center gap-4 text-sm text-slate-300">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#signals" className="hover:text-white transition">AI Signals</a>
            <a href="#risk" className="hover:text-white transition">Risk Engine</a>
            <a href="#dashboard" className="hover:text-white transition">Dashboard</a>
          </nav>
          <button className="rounded-full border border-glow px-6 py-2 text-sm text-glow shadow-glow transition hover:bg-glow/10">
            Launch App
          </button>
        </header>

        <Hero />
        <FeatureCards />
        <section id="risk" className="mt-24 grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[32px] border border-slate-800 bg-surface/80 p-8 shadow-glow backdrop-blur-xl">
            <p className="text-sm uppercase tracking-[0.24em] text-slate-400">How Lesly Works</p>
            <h2 className="mt-4 text-4xl font-semibold text-white">AI-powered market flow for safer paper signals</h2>
            <div className="mt-10 grid gap-6">
              {[
                {
                  title: 'Market Data',
                  description: 'Aggregate candle, momentum and volume flow from BTC/USDT streams.',
                },
                {
                  title: 'AI Analysis',
                  description: 'Detects patterns, trend bias and diverging timeframe signals.',
                },
                {
                  title: 'Risk Filter',
                  description: 'Rejects low-conviction setups and sideways markets.',
                },
                {
                  title: 'Paper Trade Signal',
                  description: 'Generates actionable recommendations without executing real orders.',
                },
                {
                  title: 'Dashboard Logs',
                  description: 'Visualizes every decision step, confidence score and reasoning.',
                },
              ].map((item) => (
                <div key={item.title} className="rounded-3xl border border-slate-800 bg-zinc-950/80 p-6 shadow-xl shadow-slate-950/30">
                  <p className="text-lg font-semibold text-white">{item.title}</p>
                  <p className="mt-3 text-slate-400">{item.description}</p>
                </div>
              ))}
            </div>
          </div>
          <AiStatusPanel />
        </section>

        <section id="signals" className="mt-24 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-8">
            <div className="rounded-[32px] border border-slate-800 bg-surface/80 p-8 shadow-glow backdrop-blur-xl">
              <h3 className="text-3xl font-semibold text-white">Visual Signal Intelligence</h3>
              <p className="mt-4 max-w-xl text-slate-400">
                Lesly surfaces the strongest paper signals with confidence scoring, trend alignment and risk-aware filtering — all without moving real capital.
              </p>
              <div className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  { value: '24/7', label: 'Monitoring' },
                  { value: '1H / 4H', label: 'Multi-timeframe' },
                  { value: 'Paper', label: 'Mode Only' },
                  { value: 'AI Logs', label: 'Decision History' },
                ].map((item) => (
                  <div key={item.label} className="rounded-3xl border border-slate-800 bg-[#091223] p-5 text-center">
                    <p className="text-2xl font-semibold text-white">{item.value}</p>
                    <p className="mt-2 text-sm text-slate-400">{item.label}</p>
                  </div>
                ))}
              </div>
            </div>
            <MarketSnapshotPanel />
            <SignalBoard />
            <PerformancePanel />
          </div>
          <AiLogs />
        </section>
      </div>
      <Footer />
    </main>
  );
}
