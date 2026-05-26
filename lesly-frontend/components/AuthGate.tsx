'use client';

import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import {
  fetchCurrentUser,
  fetchExchangeAccounts,
  loginUser,
  registerUser,
  saveExchangeAccount,
  type ExchangeAccount,
  type LeslyUser,
} from '../lib/pollingFetchers';

type Props = {
  children: ReactNode;
};

export default function AuthGate({ children }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [user, setUser] = useState<LeslyUser | null>(null);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [showAccountForm, setShowAccountForm] = useState(false);

  const refreshAccount = useCallback(async () => {
    const [currentUser, exchangeAccounts] = await Promise.all([fetchCurrentUser(), fetchExchangeAccounts()]);
    setUser(currentUser);
    setAccounts(exchangeAccounts);
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
      const payload = {
        email: String(form.get('email') ?? ''),
        password: String(form.get('password') ?? ''),
      };
      const response = mode === 'register'
        ? await registerUser({ ...payload, name: String(form.get('name') ?? '') })
        : await loginUser(payload);
      window.localStorage.setItem('lesly_access_token', response.access_token);
      setUser(response.user);
      setAccounts(await fetchExchangeAccounts());
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
      setAccounts(await fetchExchangeAccounts());
      setShowAccountForm(false);
      setMessage('Credenciales guardadas cifradas. Siguen en DRY_RUN hasta activarlo manualmente.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudieron guardar las credenciales.');
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    window.localStorage.removeItem('lesly_access_token');
    setUser(null);
    setAccounts([]);
  }

  if (loading) {
    return <div className="min-h-screen bg-[#020712] p-6 text-cyan-100">Cargando sesión de Lesly...</div>;
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-[#020712] px-4 py-8 text-white">
        <section className="mx-auto max-w-md rounded-[2rem] border border-cyan-400/25 bg-slate-950/80 p-6 shadow-[0_0_60px_rgba(0,140,255,0.22)]">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">Lesly AI Trading</p>
          <h1 className="mt-3 text-3xl font-black">{mode === 'login' ? 'Entrar' : 'Crear usuario'}</h1>
          <p className="mt-2 text-sm text-slate-400">Cada cuenta tendrá sus propias credenciales de exchange cifradas. Por seguridad, todo inicia en paper trading.</p>
          <form className="mt-6 space-y-4" onSubmit={submitAuth}>
            {mode === 'register' && (
              <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="name" placeholder="Nombre" required />
            )}
            <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="email" type="email" placeholder="Email" required />
            <input className="w-full rounded-2xl border border-cyan-400/20 bg-black/40 px-4 py-3 text-white outline-none focus:border-cyan-300" name="password" type="password" placeholder="Contraseña" required minLength={8} />
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
            <button className="rounded-full border border-cyan-400/25 px-4 py-2 text-xs uppercase tracking-[0.16em]" onClick={() => setShowAccountForm(!showAccountForm)}>
              Exchange
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
        {message && <p className="mx-auto mt-3 max-w-[1500px] text-xs text-cyan-200">{message}</p>}
      </div>
      {children}
    </>
  );
}
