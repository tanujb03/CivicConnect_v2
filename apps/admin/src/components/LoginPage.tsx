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
import { AlertCircle, Loader2 } from 'lucide-react';
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
    <div className="min-h-screen bg-gradient-to-br from-[#1A531A] via-[#2d6b1e] to-[#7CAE0C] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Branding card */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white tracking-tight">CivicConnect</h1>
          <p className="text-green-200 mt-1 text-sm">Municipal Operations Platform · Jharkhand</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Admin Sign In</h2>

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-5 text-sm">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="identifier">Username or Email</Label>
              <Input
                id="identifier"
                type="text"
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="admin@jharkhand.gov.in"
                required
                disabled={loading}
                className="focus-visible:ring-green-500"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
                className="focus-visible:ring-green-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="remember"
                checked={rememberMe}
                onCheckedChange={(v) => setRememberMe(v as boolean)}
                disabled={loading}
              />
              <Label htmlFor="remember" className="text-sm font-normal cursor-pointer">
                Remember me for 7 days
              </Label>
            </div>

            <Button
              type="submit"
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2.5"
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
      </div>
    </div>
  );
};

export default LoginPage;
