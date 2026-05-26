'use client';

import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import {
  fetchCurrentUser,
  fetchExchangeAccounts,
  fetchUserBotSettings,
  fetchUserPaperRuntime,
  loginUser,
  registerUser,
  resetUserPaperRuntime,
  saveExchangeAccount,
  saveUserBotSettings,
  type ExchangeAccount,
  type LeslyUser,
  type UserBotSettings,
  type UserPaperRuntime,
} from '../lib/pollingFetchers';

type Props = {
  children: ReactNode;
};

export default function AuthGate({ children }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [user, setUser] = useState<LeslyUser | null>(null);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [botSettings, setBotSettings] = useState<UserBotSettings | null>(null);
  const [paperRuntime, setPaperRuntime] = useState<UserPaperRuntime | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [showBotForm, setShowBotForm] = useState(false);

  const refreshAccount = useCallback(async () => {
    const [currentUser, exchangeAccounts, settings, runtime] = await Promise.all([
      fetchCurrentUser(),
      fetchExchangeAccounts(),
      fetchUserBotSettings(),
      fetchUserPaperRuntime(),
    ]);
    setUser(currentUser);
    setAccounts(exchangeAccounts);
    setBotSettings(settings);
    setPaperRuntime(runtime);
  }, []);

  useEffect(() => {
    const token = window.localStorage.getItem('lesly_access_token');
    if (!token) {
      setLoading(false);
      return;
    }
    refreshAccount()
      .catch(() => window.localStorage.removeItem('lesly_access_token'))
      .finally(() => setLoading(false));
  }, [refreshAccount]);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    const form = new FormData(event.currentTarget);
    try {
      const password = String(form.get('password') ?? '');
      if (mode === 'register' && password !== String(form.get('password_confirm') ?? '')) {
        setMessage('Las contraseñas no coinciden.');
        return;
      }
      const payload = {
        email: String(form.get('email') ?? ''),
        password,
      };
      const response = mode === 'register'
        ? await registerUser({ ...payload, name: String(form.get('name') ?? '') })
        : await loginUser(payload);
      window.localStorage.setItem('lesly_access_token', response.access_token);
      setUser(response.user);
      const [exchangeAccounts, settings, runtime] = await Promise.all([fetchExchangeAccounts(), fetchUserBotSettings(), fetchUserPaperRuntime()]);
      setAccounts(exchangeAccounts);
      setBotSettings(settings);
      setPaperRuntime(runtime);
      setMessage('Sesión iniciada. Lesly queda en modo paper por defecto.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo iniciar sesión.');
    } finally {
      setBusy(false);
    }
  }

  async function submitExchange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    const form = new FormData(event.currentTarget);
    try {
      await saveExchangeAccount({
        exchange: String(form.get('exchange') ?? 'kraken'),
        api_key: String(form.get('api_key') ?? ''),
        api_secret: String(form.get('api_secret') ?? ''),
        passphrase: String(form.get('passphrase') ?? ''),
        account_label: 'main',
        dry_run: true,
      });
      const [exchangeAccounts, runtime] = await Promise.all([fetchExchangeAccounts(), fetchUserPaperRuntime()]);
      setAccounts(exchangeAccounts);
      setPaperRuntime(runtime);
      setShowAccountForm(false);
      setMessage('Credenciales guardadas cifradas. Siguen en DRY_RUN hasta activarlo manualmente.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudieron guardar las credenciales.');
    } finally {
      setBusy(false);
    }
  }

  async function submitBotSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    const form = new FormData(event.currentTarget);
    try {
      const settings = await saveUserBotSettings({
        active: form.get('active') === 'on',
        selected_exchange: String(form.get('selected_exchange') ?? 'kraken'),
        symbols: Array.from(form.getAll('symbols')).join(',') || 'BTC,ETH',
        paper_balance: Number(form.get('paper_balance') ?? 5000),
        max_open_positions: Number(form.get('max_open_positions') ?? 2),
        risk_profile: String(form.get('risk_profile') ?? 'balanced'),
      });
      setBotSettings(settings);
      setPaperRuntime(await fetchUserPaperRuntime());
      setShowBotForm(false);
      setMessage('Perfil paper del usuario actualizado.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo guardar el perfil del bot.');
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    window.localStorage.removeItem('lesly_access_token');
    setUser(null);
    setAccounts([]);
    setBotSettings(null);
    setPaperRuntime(null);
  }

  async function resetRuntime() {
    setBusy(true);
    setMessage('');
    try {
      const runtime = await resetUserPaperRuntime();
      setPaperRuntime(runtime);
      setMessage('Runtime paper reiniciado para esta cuenta.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo reiniciar el runtime paper.');
    } finally {
      setBusy(false);
    }
  }

  const money = (value: number | undefined) => `$${(value ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (loading) {
    return <div className="min-h-screen bg-[#020712] p-6 text-cyan-100">Cargando sesión de Lesly...</div>;
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-[#020712] px-4 py-8 text-white">
        <section className="mx-auto max-w-md rounded-[2rem] border border-cyan-400/25 bg-slate-950/80 p-6 shadow-[0_0_60px_rgba(0,140,255,0.22)]">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">Lesly AI Trading</p>
          <h1 className="mt-3 text-3xl font-black">{mode === 'login' ? 'Entrar' : 'Crear usuario'}</h1>
          <p className="mt-2 text-sm text-slate-400">Cada cuenta tendrá sus propias credenciales de exchange cifradas.</p>
          <form className="mt-6 space-y-4" onSubmit={submitAuth}>
            {mode === 'register' && (
              <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="name" placeholder="Nombre" required />
            )}
            <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="email" type="email" placeholder="Email" required />
            <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="password" type="password" placeholder="Contraseña" required minLength={8} />
            {mode === 'register' && (
              <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="password_confirm" type="password" placeholder="Confirmar contraseña" required minLength={8} />
            )}
            <button className="w-full rounded-2xl bg-cyan-400 px-4 py-3 font-black uppercase tracking-[0.18em] text-slate-950 disabled:opacity-60" disabled={busy}>
              {busy ? 'Procesando...' : mode === 'login' ? 'Entrar' : 'Crear cuenta'}
            </button>
          </form>
          <button className="mt-4 text-sm text-cyan-200" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? 'Crear una cuenta nueva' : 'Ya tengo cuenta'}
          </button>
          {message && <p className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-3 text-sm text-cyan-100">{message}</p>}
        </section>
      </main>
    );
  }

  return (
    <>
      <div className="border-b border-cyan-400/10 bg-slate-950 px-4 py-3 text-sm text-cyan-100">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3">
          <span>{user.name} · {user.email} · Paper trading</span>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100">
              {paperRuntime ? `${paperRuntime.open_positions_count}/${paperRuntime.max_open_positions} abiertas · ${money(paperRuntime.account.equity)}` : 'Runtime paper'}
            </span>
            <button className="rounded-full border border-cyan-400/25 px-4 py-2 text-xs uppercase tracking-[0.16em]" onClick={() => setShowAccountForm(!showAccountForm)}>
              Exchange
            </button>
            <button className="rounded-full border border-cyan-400/25 px-4 py-2 text-xs uppercase tracking-[0.16em]" onClick={() => setShowBotForm(!showBotForm)}>
              Bot
            </button>
            <button className="rounded-full border border-rose-400/25 px-4 py-2 text-xs uppercase tracking-[0.16em] text-rose-200" onClick={logout}>
              Salir
            </button>
          </div>
        </div>
        {showAccountForm && (
          <form className="mx-auto mt-4 grid max-w-[1500px] gap-3 rounded-3xl border border-cyan-400/20 bg-black/30 p-4 md:grid-cols-5" onSubmit={submitExchange}>
            <select className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="exchange" defaultValue="kraken">
              <option value="kraken">Kraken</option>
              <option value="coinbase">Coinbase</option>
              <option value="binance">Binance</option>
              <option value="okx">OKX</option>
            </select>
            <input className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="api_key" placeholder="API key" required />
            <input className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="api_secret" placeholder="API secret" required />
            <input className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="passphrase" placeholder="Passphrase opcional" />
            <button className="rounded-2xl bg-emerald-400 px-3 py-3 font-black uppercase tracking-[0.14em] text-slate-950" disabled={busy}>Guardar</button>
            <p className="md:col-span-5 text-xs text-slate-400">
              Cuentas guardadas: {accounts.length ? accounts.map((account) => `${account.exchange} ${account.api_key_preview}`).join(' · ') : 'ninguna todavía'}.
            </p>
          </form>
        )}
        {showBotForm && (
          <form className="mx-auto mt-4 grid max-w-[1500px] gap-3 rounded-3xl border border-cyan-400/20 bg-black/30 p-4 md:grid-cols-6" onSubmit={submitBotSettings}>
            <select className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="selected_exchange" defaultValue={botSettings?.selected_exchange ?? 'kraken'}>
              <option value="kraken">Kraken</option>
              <option value="coinbase">Coinbase</option>
              <option value="binance">Binance</option>
              <option value="okx">OKX</option>
            </select>
            <input className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="paper_balance" type="number" min="1" defaultValue={botSettings?.paper_balance ?? 5000} placeholder="Capital paper" />
            <select className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="max_open_positions" defaultValue={botSettings?.max_open_positions ?? 2}>
              <option value="1">1 posición</option>
              <option value="2">2 posiciones</option>
            </select>
            <select className="rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3" name="risk_profile" defaultValue={botSettings?.risk_profile ?? 'balanced'}>
              <option value="conservative">Conservador</option>
              <option value="balanced">Balanceado</option>
              <option value="aggressive">Agresivo</option>
            </select>
            <label className="flex items-center gap-2 rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3">
              <input type="checkbox" name="symbols" value="BTC" defaultChecked={(botSettings?.symbols ?? 'BTC,ETH').includes('BTC')} />
              BTC
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-cyan-400/20 bg-slate-950 px-3 py-3">
              <input type="checkbox" name="symbols" value="ETH" defaultChecked={(botSettings?.symbols ?? 'BTC,ETH').includes('ETH')} />
              ETH
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-3 py-3 md:col-span-2">
              <input type="checkbox" name="active" defaultChecked={botSettings?.active ?? false} />
              Bot paper activo para esta cuenta
            </label>
            <button className="rounded-2xl bg-cyan-400 px-3 py-3 font-black uppercase tracking-[0.14em] text-slate-950 md:col-span-2" disabled={busy}>Guardar perfil</button>
            <p className="md:col-span-6 text-xs text-slate-400">
              Este perfil separa configuración por usuario. El runtime paper propio ya está preparado; la ejecución multiusuario del worker se conectará en la próxima fase.
            </p>
          </form>
        )}
        {paperRuntime && (
          <section className="mx-auto mt-4 grid max-w-[1500px] gap-3 rounded-3xl border border-cyan-400/20 bg-black/30 p-4 text-xs md:grid-cols-6">
            <div>
              <p className="uppercase tracking-[0.22em] text-slate-500">Exchange</p>
              <p className="mt-1 font-bold text-cyan-100">{paperRuntime.active_exchange.toUpperCase()} · {paperRuntime.exchange_ready ? 'conectado' : 'sin API'}</p>
            </div>
            <div>
              <p className="uppercase tracking-[0.22em] text-slate-500">Símbolos</p>
              <p className="mt-1 font-bold text-cyan-100">{paperRuntime.active_symbols.join(', ')}</p>
            </div>
            <div>
              <p className="uppercase tracking-[0.22em] text-slate-500">Disponible</p>
              <p className="mt-1 font-bold text-emerald-200">{money(paperRuntime.account.cash_balance)}</p>
            </div>
            <div>
              <p className="uppercase tracking-[0.22em] text-slate-500">Margen</p>
              <p className="mt-1 font-bold text-amber-200">{money(paperRuntime.account.margin_reserved)}</p>
            </div>
            <div>
              <p className="uppercase tracking-[0.22em] text-slate-500">Último evento</p>
              <p className="mt-1 truncate font-bold text-cyan-100">{paperRuntime.latest_events[0]?.message ?? 'Sin eventos propios todavía.'}</p>
            </div>
            <button className="rounded-2xl border border-amber-300/30 px-3 py-3 font-black uppercase tracking-[0.14em] text-amber-100 disabled:opacity-50" onClick={resetRuntime} disabled={busy}>
              Reset paper
            </button>
          </section>
        )}
        {message && <p className="mx-auto mt-3 max-w-[1500px] text-xs text-cyan-200">{message}</p>}
      </div>
      {children}
    </>
  );
}
