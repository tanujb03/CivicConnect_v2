import React, { createContext, useContext } from 'react';
import { useAuth, AuthState } from '../hooks/useAuth';
import type { AuthUser, OtpRequestPayload, OtpVerifyPayload } from '../types';

interface AuthContextValue {
  state: AuthState;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  requestOtp: (payload: OtpRequestPayload) => Promise<void>;
  verifyOtp: (payload: OtpVerifyPayload) => Promise<AuthUser>;
  demoLogin: () => Promise<AuthUser | undefined>;
  authenticateAsCitizen: (details?: { name?: string; locality?: string; language?: string }) => Promise<AuthUser | undefined>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}
