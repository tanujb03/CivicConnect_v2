/**
 * useAuth — Authentication state hook
 *
 * Manages token storage, user session, and auth flow state.
 * Wraps authApi calls from the API client.
 */

import { useState, useEffect, useCallback } from 'react';
import { authApi, storeTokens, storeUser, clearTokens, getStoredUser, getAccessToken } from '../api/client';
import type { AuthUser, OtpRequestPayload, OtpVerifyPayload } from '../types';

export type AuthState =
  | { status: 'loading' }
  | { status: 'unauthenticated' }
  | { status: 'authenticated'; user: AuthUser }
  | { status: 'error'; message: string };

const MOCK_TOKEN_PREFIX = 'mock-access-token';

export function useAuth() {
  const [state, setState] = useState<AuthState>({ status: 'loading' });

  // Restore session on mount
  useEffect(() => {
    (async () => {
      try {
        const stored = await getStoredUser();
        const token = await getAccessToken();
        if (stored && token) {
          // If it's a mock/demo token, trust the stored user directly without network call
          if (token.startsWith(MOCK_TOKEN_PREFIX) || token.startsWith('mock-')) {
            setState({ status: 'authenticated', user: stored });
            return;
          }
          // Otherwise verify with the server
          const fresh = await authApi.me().catch(() => null);
          if (fresh && fresh.id) {
            await storeUser(fresh);
            setState({ status: 'authenticated', user: fresh });
          } else {
            await clearTokens();
            setState({ status: 'unauthenticated' });
          }
        } else {
          setState({ status: 'unauthenticated' });
        }
      } catch {
        setState({ status: 'unauthenticated' });
      }
    })();
  }, []);

  const requestOtp = useCallback(async (payload: OtpRequestPayload) => {
    setState(s => s.status === 'authenticated' ? s : { status: 'loading' });
    try {
      await authApi.requestOtp(payload);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to send OTP';
      setState({ status: 'error', message: msg });
      throw err;
    } finally {
      setState(s => s.status === 'loading' ? { status: 'unauthenticated' } : s);
    }
  }, []);

  const verifyOtp = useCallback(async (payload: OtpVerifyPayload) => {
    setState({ status: 'loading' });
    try {
      const { user, ...tokens } = await authApi.verifyOtp(payload);
      await storeTokens(tokens);
      await storeUser(user);
      setState({ status: 'authenticated', user });
      return user;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Invalid OTP';
      setState({ status: 'error', message: msg });
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore — clear tokens regardless
    } finally {
      await clearTokens();
      setState({ status: 'unauthenticated' });
    }
  }, []);

  const demoLogin = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const { user } = await authApi.demoLogin();
      setState({ status: 'authenticated', user });
      return user;
    } catch {
      setState({ status: 'unauthenticated' });
    }
  }, []);

  const authenticateAsCitizen = useCallback(async (details?: { name?: string; locality?: string; language?: string }) => {
    setState({ status: 'loading' });
    try {
      const user: AuthUser = {
        id: 'citizen-demo-1',
        name: details?.name?.trim() || 'Priya Sharma',
        phone: '+91 98765 43210',
        email: 'priya.sharma@example.com',
        role: 'CITIZEN',
        locality: details?.locality?.trim() || 'Kanke Road, Ranchi',
        ward: 'Ward 15',
        language: details?.language || 'en',
      };
      const tokens = {
        access_token: 'mock-access-token-demo',
        refresh_token: 'mock-refresh-token-demo',
        expires_in: 86400,
      };
      await storeTokens(tokens);
      await storeUser(user);
      setState({ status: 'authenticated', user });
      return user;
    } catch {
      setState({ status: 'unauthenticated' });
    }
  }, []);

  const user = state.status === 'authenticated' ? state.user : null;
  const isAuthenticated = state.status === 'authenticated';
  const isLoading = state.status === 'loading';

  return { state, user, isAuthenticated, isLoading, requestOtp, verifyOtp, demoLogin, authenticateAsCitizen, logout };
}
