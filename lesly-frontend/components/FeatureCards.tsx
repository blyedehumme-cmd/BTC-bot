const cards = [
  {
    title: 'Real-time AI Analysis',
    description: 'Continuous market scanning with intelligent bias detection and signal scoring.',
  },
  {
    title: 'Multi-timeframe Strategy',
    description: 'Combine 5m, 15m, 1H, 4H and daily views for safer decisions.',
  },
  {
    title: 'Intelligent Risk Management',
    description: 'Dynamic filters that reduce exposure in sideways or volatile conditions.',
  },
  {
    title: 'Paper Trading Mode',
    description: 'Simulated execution only — no real funds are moved or risked.',
  },
  {
    title: 'Telegram Alerts',
    description: 'Instant signal notifications and score updates for your watchlist.',
  },
  {
    title: '24/7 Automated Monitoring',
    description: 'A watchful system that never sleeps and logs every decision.',
  },
];

export default function FeatureCards() {
  return (
    <section id="features" className="mt-20">
      <div className="mb-10 flex flex-col gap-3">
        <p className="text-sm uppercase tracking-[0.36em] text-slate-400">Core Features</p>
        <h2 className="text-4xl font-semibold text-white">Designed for premium AI paper trading.</h2>
        <p className="max-w-2xl text-slate-400">
          Lesly blends a futuristic trading interface with risk-first signal generation to keep your strategy transparent and controlled.
        </p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <div key={card.title} className="rounded-[28px] border border-slate-800 bg-[#07111f]/90 p-6 shadow-glow backdrop-blur-xl">
            <p className="text-xl font-semibold text-white">{card.title}</p>
            <p className="mt-3 text-slate-400">{card.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
