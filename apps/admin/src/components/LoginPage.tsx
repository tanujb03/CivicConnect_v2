/**
 * A01 — Admin Login
 * Role-aware authentication entry point.
 * On success: stores token in localStorage, navigates to dashboard.
 * On integration: calls authApi.login() instead of mock.
 */
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { AlertCircle, Loader2, Shield, Sparkles, Lock, Mail } from 'lucide-react';
import { setTokens } from '../lib/api';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard';

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier || !password) return;

    setLoading(true);
    setError(null);

    try {
      // TODO: replace mock with real API call when backend is ready:
      // const session = await authApi.login(identifier, password);
      // setTokens(session.access_token, session.refresh_token);

      // Mock: store a placeholder token so ProtectedRoute lets us through
      setTokens('mock-access-token', 'mock-refresh-token');
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
         style={{ background: 'linear-gradient(145deg, #051a08 0%, #0d4a1a 30%, #1a6b2e 60%, #2a8a42 100%)' }}>
      
      {/* Animated background orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-96 h-96 rounded-full animate-float"
             style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.1) 0%, transparent 70%)', animationDelay: '0s' }} />
        <div className="absolute bottom-20 right-20 w-80 h-80 rounded-full animate-float"
             style={{ background: 'radial-gradient(circle, rgba(108,199,122,0.08) 0%, transparent 70%)', animationDelay: '2s', animationDuration: '8s' }} />
        <div className="absolute top-1/2 left-1/3 w-64 h-64 rounded-full animate-float"
             style={{ background: 'radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%)', animationDelay: '4s', animationDuration: '10s' }} />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 opacity-[0.03]"
             style={{
               backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                                 linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
               backgroundSize: '80px 80px',
             }} />
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Branding */}
        <div className="text-center mb-8 page-enter">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-full px-4 py-1.5 border border-white/10 mb-5">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-xs text-white/60 font-medium">Secure Government Portal</span>
          </div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight" style={{ textShadow: '0 2px 10px rgba(0,0,0,0.2)' }}>
            CivicConnect
          </h1>
          <p className="text-emerald-300/40 mt-2 text-sm font-medium">Municipal Operations Platform · Jharkhand</p>
        </div>

        {/* Login Card */}
        <div className="bg-white/95 backdrop-blur-xl rounded-3xl shadow-2xl p-8 page-enter" style={{ animationDelay: '0.1s', boxShadow: '0 30px 80px rgba(0,0,0,0.3), 0 0 1px rgba(0,0,0,0.1)' }}>
          <div className="flex items-center gap-2 mb-6">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                 style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)' }}>
              <Lock className="w-4 h-4 text-white" />
            </div>
            <h2 className="text-xl font-bold text-gray-800">Admin Sign In</h2>
          </div>

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-100 text-red-700 rounded-xl p-3.5 mb-5 text-sm animate-scale-in">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="identifier" className="text-sm font-semibold text-gray-700">Username or Email</Label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="identifier"
                  type="text"
                  autoComplete="username"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="admin@jharkhand.gov.in"
                  required
                  disabled={loading}
                  className="pl-10 h-12 rounded-xl border-gray-200 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-400 transition-all"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-semibold text-gray-700">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  className="pl-10 h-12 rounded-xl border-gray-200 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-400 transition-all"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="remember"
                checked={rememberMe}
                onCheckedChange={(v) => setRememberMe(v as boolean)}
                disabled={loading}
                className="border-gray-300 data-[state=checked]:bg-emerald-600 data-[state=checked]:border-emerald-600"
              />
              <Label htmlFor="remember" className="text-sm font-normal text-gray-500 cursor-pointer">
                Remember me for 7 days
              </Label>
            </div>

            <Button
              type="submit"
              className="w-full h-12 rounded-xl text-white font-bold text-[15px] transition-all duration-300 hover:shadow-lg"
              style={{ 
                background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)',
                boxShadow: '0 4px 20px rgba(22, 163, 74, 0.3)',
              }}
              disabled={loading || !identifier || !password}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-gray-400">
            Access restricted to authorized government personnel only.
          </p>
        </div>

        {/* Footer */}
        <div className="text-center mt-6 page-enter" style={{ animationDelay: '0.2s' }}>
          <div className="flex items-center justify-center gap-2 text-white/30 text-xs">
            <Sparkles className="w-3 h-3" />
            <span>Powered by Digital India Initiative</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
