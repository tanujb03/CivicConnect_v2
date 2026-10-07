/**
 * A01 — Admin Login
 * Split screen: wine brand panel (headline pop, three counters, ticker)
 * and a sign-in card. Intro curtain plays once per session.
 *
 * Data: POST /auth/login with identifier and password, then GET /auth/me.
 * Demo buttons that prefill demo accounts appear only in development.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AlertCircle, Loader2, Lock, Mail, ArrowUpRight } from 'lucide-react';
import { setTokens } from '../lib/api';

// Demo accounts shown only in development mode
const DEMO_ACCOUNTS = [
  { label: 'City Admin', identifier: 'admin@ranchi.gov.in', password: 'demo1234' },
  { label: 'Dept. Operator', identifier: 'operator@ranchi.gov.in', password: 'demo1234' },
  { label: 'Ward Officer', identifier: 'ward@ranchi.gov.in', password: 'demo1234' },
];

// Ticker items — in production these come from real incidents and hotspots
const TICKER_ITEMS = [
  '12 new cases in last hour',
  'Ward W12 hotspot alert — road damage cluster',
  'SLA breach approaching in 3 cases',
  'Sanitation backlog in W18 above baseline',
  'Field crew dispatched to W07 lighting failure',
  'Resolution evidence pending for CC-1042',
];

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard';

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCurtain, setShowCurtain] = useState(false);

  // Intro curtain plays once per session
  useEffect(() => {
    const curtainShown = sessionStorage.getItem('cc-curtain-shown');
    if (!curtainShown) {
      setShowCurtain(true);
      sessionStorage.setItem('cc-curtain-shown', '1');
      const timer = setTimeout(() => setShowCurtain(false), 1800);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier || !password) return;

    setLoading(true);
    setError(null);

    try {
      // TODO: replace with real API call: POST /auth/login
      // const session = await authApi.login(identifier, password);
      // setTokens(session.access_token, session.refresh_token);
      setTokens('mock-access-token', 'mock-refresh-token');
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const e = err as { message?: string; code?: string };
      // Show a message per error.code as the plan specifies
      if (e?.code === 'INVALID_CREDENTIALS') {
        setError('Invalid username or password. Please try again.');
      } else if (e?.code === 'ACCOUNT_LOCKED') {
        setError('Account temporarily locked. Try again in 15 minutes.');
      } else {
        setError(e?.message ?? 'Login failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  const prefillDemo = (account: typeof DEMO_ACCOUNTS[0]) => {
    setIdentifier(account.identifier);
    setPassword(account.password);
    setError(null);
  };

  const isDev = import.meta.env.DEV;

  return (
    <>
      {/* Intro curtain — wine panel with rosette and wordmark, slides up once */}
      {showCurtain && (
        <div className="cc-curtain">
          <div className="text-center">
            <div className="relative inline-block mb-4">
              <div
                className="w-16 h-16 rounded-xl border-2 border-on-wine/30 flex items-center justify-center mx-auto"
                style={{ background: 'var(--rust-deep)' }}
              >
                <span className="text-on-wine font-display text-xl">CC</span>
              </div>
              <div
                className="absolute inset-[-8px] rounded-2xl border-2 border-dashed border-on-wine/20 cc-rosette pointer-events-none"
                aria-hidden="true"
              />
            </div>
            <h1 className="font-display text-3xl text-on-wine tracking-tight">CivicConnect</h1>
            <p className="font-mono text-xs text-on-wine/50 uppercase tracking-widest mt-2">
              Municipal Operations Platform
            </p>
          </div>
        </div>
      )}

      {/* Main login screen — split layout */}
      <div className="min-h-screen flex" style={{ background: 'var(--ground)' }}>
        {/* Left: wine brand panel */}
        <div
          className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
          style={{ background: 'var(--wine)' }}
        >
          {/* Top: logo */}
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-lg border-2 border-on-wine/30 flex items-center justify-center"
              style={{ background: 'var(--rust-deep)' }}
            >
              <span className="text-on-wine font-display text-sm">CC</span>
            </div>
            <div>
              <h2 className="font-display text-lg text-on-wine tracking-tight">CivicConnect</h2>
              <p className="text-[10px] font-mono text-on-wine/40 uppercase tracking-wider">Admin Portal</p>
            </div>
          </div>

          {/* Center: headline pop with three counters */}
          <div className="flex-1 flex flex-col justify-center">
            <h1 className="cc-headline-pop font-display text-on-wine leading-[1.05]" style={{ fontSize: 'clamp(2.5rem, 5vw, 4rem)' }}>
              Civic Intelligence.
              <br />
              <span className="font-script text-lime" style={{ fontSize: '0.7em', transform: 'rotate(-2deg)', display: 'inline-block' }}>
                Real Action.
              </span>
            </h1>

            {/* Three counters */}
            <div className="flex gap-6 mt-10">
              {[
                { value: '12K+', label: 'Cases Resolved' },
                { value: '34', label: 'Active Wards' },
                { value: '98%', label: 'SLA Compliance' },
              ].map((stat, i) => (
                <div key={stat.label} className="cc-fade-up" style={{ '--stagger-index': i } as React.CSSProperties}>
                  <div className="font-display text-2xl text-lime">{stat.value}</div>
                  <div className="font-mono text-[10px] text-on-wine/50 uppercase tracking-wider mt-1">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom: ticker */}
          <div className="cc-ticker border-t-2 border-on-wine/10 pt-4 -mx-12 px-12">
            <div className="cc-ticker-track gap-8">
              {/* Two identical groups for seamless loop */}
              {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
                <span key={i} className="flex items-center gap-2 text-on-wine/40 text-xs font-mono whitespace-nowrap shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-lime shrink-0" />
                  {item}
                </span>
              ))}
            </div>
          </div>

          {/* Decorative sticker */}
          <div className="cc-sticker-fly absolute top-8 right-8">
            <div className="cc-sticker" style={{ fontSize: '10px' }}>
              Direction A
            </div>
          </div>
        </div>

        {/* Right: sign-in card */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="w-full max-w-md">
            {/* Mobile-only branding (shown when wine panel is hidden) */}
            <div className="lg:hidden text-center mb-8 cc-fade-up">
              <div
                className="w-12 h-12 rounded-lg border-2 border-ink flex items-center justify-center mx-auto mb-3"
                style={{ background: 'var(--wine)' }}
              >
                <span className="text-on-wine font-display text-base">CC</span>
              </div>
              <h1 className="font-display text-2xl text-ink">CivicConnect</h1>
              <p className="font-mono text-xs text-muted uppercase tracking-wider mt-1">Admin Portal</p>
            </div>

            {/* Sign-in card */}
            <div className="cc-card p-8 cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
              <div className="flex items-center gap-3 mb-6">
                <div
                  className="w-9 h-9 rounded-md border-2 border-ink flex items-center justify-center"
                  style={{ background: 'var(--ink)' }}
                >
                  <Lock className="w-4 h-4" style={{ color: 'var(--on-wine)' }} />
                </div>
                <div>
                  <h2 className="text-lg font-display text-ink">Sign In</h2>
                  <p className="text-xs font-mono text-muted">Authorized personnel only</p>
                </div>
              </div>

              {/* Error banner */}
              {error && (
                <div className="cc-banner-error flex items-start gap-2 mb-5 text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-1.5">
                  <label htmlFor="identifier" className="text-sm font-semibold text-ink">
                    Username or Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                    <input
                      id="identifier"
                      type="text"
                      autoComplete="username"
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder="admin@ranchi.gov.in"
                      required
                      disabled={loading}
                      className="w-full pl-10 pr-4 py-3 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted disabled:opacity-50"
                      style={{ minHeight: '44px' }}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="password" className="text-sm font-semibold text-ink">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                    <input
                      id="password"
                      type="password"
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      disabled={loading}
                      className="w-full pl-10 pr-4 py-3 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted disabled:opacity-50"
                      style={{ minHeight: '44px' }}
                    />
                  </div>
                </div>

                {/* Submit button with roll effect */}
                <button
                  type="submit"
                  disabled={loading || !identifier || !password}
                  className="cc-btn cc-btn-primary w-full justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ minHeight: '48px' }}
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Signing in...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In</span>
                      <ArrowUpRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </form>

              {/* Demo prefill buttons — only in development */}
              {isDev && (
                <div className="mt-6 pt-5 border-t-2 border-dot">
                  <p className="text-xs font-mono text-muted uppercase tracking-wider mb-3">Demo Accounts</p>
                  <div className="flex flex-wrap gap-2">
                    {DEMO_ACCOUNTS.map((account) => (
                      <button
                        key={account.label}
                        type="button"
                        onClick={() => prefillDemo(account)}
                        className="cc-chip hover:bg-lime-tint transition-colors cursor-pointer"
                      >
                        {account.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <p className="text-center text-xs font-mono text-muted mt-6 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
              Access restricted to authorized government personnel.
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default LoginPage;
