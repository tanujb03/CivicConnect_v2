/**
 * Overlooker Login — O01-Login
 * Split panel: left wine brand panel with headline pop, right login form.
 * Same Direction A aesthetic as admin but with OVERLOOKER chip.
 */
import React, { useState } from 'react';
import { Eye, EyeOff, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const LoginPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    jurisdiction: '',
  });
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    setTimeout(() => {
      if (formData.username && formData.password && formData.jurisdiction) {
        localStorage.setItem('civic_auth_token', 'demo-token-123');
        localStorage.setItem('civic_user_role', 'overlooker');
        localStorage.setItem('civic_user_name', formData.username);
        localStorage.setItem('civic_user_jurisdiction', formData.jurisdiction);
        window.location.href = '/';
      }
      setIsLoading(false);
    }, 800);
  };

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--ground)' }}>
      {/* ── Left: Wine brand panel ────────────────────────────────────── */}
      <div
        className="hidden lg:flex lg:w-[45%] flex-col justify-between p-12"
        style={{ background: 'var(--wine)', color: 'var(--on-wine)' }}
      >
        <div>
          {/* Logo mark */}
          <div className="flex items-center gap-3 mb-12">
            <div
              className="w-10 h-10 rounded-md border-2 border-on-wine/30 flex items-center justify-center font-display text-lg"
              style={{ background: 'var(--rust-deep)' }}
            >
              CC
            </div>
            <span className="font-display text-lg">CivicConnect</span>
          </div>

          {/* Headline */}
          <h1 className="font-display text-4xl leading-tight cc-headline-pop">
            City Oversight<br />
            Dashboard
          </h1>
          <p className="text-on-wine/60 mt-4 text-sm max-w-sm cc-fade-up" style={{ '--stagger-index': 1 } as React.CSSProperties}>
            Monitor city operations in real-time. Read-only access to all municipal data,
            analytics, and AI-powered insights.
          </p>

          {/* Sticker */}
          <div className="mt-8 cc-fade-up" style={{ '--stagger-index': 2 } as React.CSSProperties}>
            <span className="cc-chip text-[11px] border-on-wine/30 bg-rust-deep/50 text-on-wine/80 tracking-wider uppercase">
              OVERLOOKER PORTAL
            </span>
          </div>
        </div>

        {/* Bottom stat */}
        <div className="cc-fade-up" style={{ '--stagger-index': 3 } as React.CSSProperties}>
          <p className="text-on-wine/40 text-xs font-mono">
            Read-only access. No case mutations allowed.
          </p>
        </div>
      </div>

      {/* ── Right: Login form ────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile header */}
          <div className="lg:hidden text-center mb-8">
            <div
              className="w-12 h-12 rounded-md border-2 border-ink mx-auto mb-4 flex items-center justify-center font-display text-lg"
              style={{ background: 'var(--wine)', color: 'var(--on-wine)' }}
            >
              CC
            </div>
            <h1 className="font-display text-2xl text-ink">CivicConnect</h1>
            <span className="cc-chip text-[9px] mt-2 bg-lime-tint">OVERLOOKER</span>
          </div>

          <div className="cc-card p-8">
            <h2 className="font-display text-xl text-ink mb-1">Sign in</h2>
            <p className="text-xs font-mono text-muted mb-6">Overlooker read-only access</p>

            <form onSubmit={handleLogin} className="space-y-5">
              {/* Username */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">Username</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData(prev => ({ ...prev, username: e.target.value }))}
                  placeholder="Enter username"
                  className="w-full px-4 py-3 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted"
                  style={{ minHeight: '44px' }}
                  required
                  autoFocus
                />
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                    placeholder="Enter password"
                    className="w-full px-4 py-3 pr-12 bg-ground border-2 border-ink rounded-md text-sm text-ink placeholder-muted"
                    style={{ minHeight: '44px' }}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Jurisdiction */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono text-muted uppercase">Jurisdiction</label>
                <select
                  value={formData.jurisdiction}
                  onChange={(e) => setFormData(prev => ({ ...prev, jurisdiction: e.target.value }))}
                  className="w-full px-4 py-3 bg-ground border-2 border-ink rounded-md text-sm text-ink"
                  style={{ minHeight: '44px' }}
                  required
                >
                  <option value="">Select jurisdiction</option>
                  <option value="ranchi">Ranchi Municipal Corporation</option>
                  <option value="jamshedpur">Jamshedpur Municipal</option>
                  <option value="dhanbad">Dhanbad Municipal</option>
                </select>
              </div>

              <button
                type="submit"
                className="cc-btn cc-btn-primary w-full justify-center text-sm"
                disabled={isLoading}
              >
                {isLoading ? 'Signing in...' : 'Sign in to Overlooker'}
              </button>
            </form>

            <p className="text-[10px] font-mono text-muted text-center mt-4">
              Contact city admin for access credentials.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;