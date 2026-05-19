type TradingPanelProps = {
  symbol?: string;
  price?: number;
  signal?: string;
};

export default function TradingPanel({ symbol = 'BTC/USDT', price = 63498, signal = 'LONG' }: TradingPanelProps) {
  return (
    <div className="relative overflow-hidden rounded-[32px] border border-slate-800 bg-[#02050e]/95 p-6 shadow-glow sm:p-8">
      <div className="absolute -left-16 top-10 h-72 w-72 rounded-full bg-glow/10 blur-3xl" />
      <div className="relative z-10 flex items-center justify-between text-sm text-slate-400">
        <div>
          <p className="uppercase tracking-[0.3em]">{symbol}</p>
          <p className="mt-2 text-3xl font-semibold text-white">${price.toLocaleString()}</p>
        </div>
        <div className="rounded-full border border-glow/50 bg-slate-950/40 px-4 py-2 text-xs uppercase tracking-[0.18em] text-glow">
          Signal: {signal}
        </div>
      </div>
      <div className="mt-8 rounded-[28px] border border-slate-800 bg-[#081020] p-5">
        <div className="flex items-center justify-between text-xs uppercase tracking-[0.22em] text-slate-500">
          <span>1H trend</span>
          <span>Paper Mode</span>
        </div>
        <div className="mt-5 h-[280px] w-full overflow-hidden rounded-3xl bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 p-4 shadow-inner shadow-slate-950/50">
          <div className="relative h-full w-full rounded-3xl bg-[radial-gradient(circle_at_top,_rgba(0,212,255,0.15),transparent_25%)]">
            <div className="absolute left-6 top-4 h-[calc(100%-4rem)] w-full">
              {[20, 18, 22, 16, 25, 19, 24, 21, 27, 23].map((height, index) => (
                <div
                  key={index}
                  style={{
                    bottom: 0,
                    left: `${index * 9}%`,
                    height: `${height * 3}px`,
                  }}
                  className="absolute w-4 rounded-t-2xl bg-gradient-to-t from-cyan-400/90 to-slate-300/20"
                />
              ))}
            </div>
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-transparent via-glow/60 to-transparent" />
          </div>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {[
            { label: 'Confidence', value: '87%' },
            { label: 'Risk Level', value: 'Low' },
            { label: 'Support', value: '$63,120' },
            { label: 'Resistance', value: '$63,860' },
          ].map((item) => (
            <div key={item.label} className="rounded-3xl bg-slate-950/80 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{item.label}</p>
              <p className="mt-2 text-lg font-semibold text-white">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
