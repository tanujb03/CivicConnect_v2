/**
 * CivicConnect Field Worker — Design System & Theme
 *
 * Optimized for high-glare outdoor usability, large touch targets,
 * and high-contrast status signifiers.
 */

export const Colors = {
  // Brand / Primary: Municipal Field Work
  brand: {
    50: '#F0FDF4',
    100: '#DCFCE7',
    200: '#BBF7D0',
    300: '#86EFAC',
    400: '#4ADE80',
    500: '#22C55E',
    600: '#16A34A',
    700: '#15803D',
    800: '#166534',
    900: '#14532D',
  },
  // Work Order / Action Accent (Amber / Safety Gold)
  action: {
    50: '#FFFBEB',
    100: '#FEF3C7',
    200: '#FDE68A',
    300: '#FCD34D',
    400: '#FBBF24',
    500: '#F59E0B',
    600: '#D97706',
    700: '#B45309',
    800: '#92400E',
    900: '#78350F',
  },
  neutral: {
    0: '#FFFFFF',
    50: '#F8FAFC',
    100: '#F1F5F9',
    200: '#E2E8F0',
    300: '#CBD5E1',
    400: '#94A3B8',
    500: '#64748B',
    600: '#475569',
    700: '#334155',
    800: '#1E293B',
    900: '#0F172A',
  },
  surface: '#FFFFFF',
  background: '#F8FAFC',
  border: '#E2E8F0',
  error: {
    50: '#FEF2F2',
    300: '#FCA5A5',
    500: '#EF4444',
    700: '#B91C1C',
  },
  success: {
    50: '#F0FDF4',
    500: '#22C55E',
    700: '#15803D',
  },
  info: {
    50: '#F0F9FF',
    500: '#0EA5E9',
    700: '#0369A1',
  },
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const Radii = {
  sm: 6,
  md: 10,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const Typography = {
  display: { fontSize: 28, fontWeight: '800' as const, lineHeight: 34 },
  headline: { fontSize: 22, fontWeight: '700' as const, lineHeight: 28 },
  titleLarge: { fontSize: 18, fontWeight: '700' as const, lineHeight: 24 },
  titleMedium: { fontSize: 16, fontWeight: '600' as const, lineHeight: 22 },
  titleSmall: { fontSize: 14, fontWeight: '600' as const, lineHeight: 20 },
  bodyLarge: { fontSize: 16, fontWeight: '400' as const, lineHeight: 22 },
  bodyMedium: { fontSize: 14, fontWeight: '400' as const, lineHeight: 20 },
  bodySmall: { fontSize: 12, fontWeight: '400' as const, lineHeight: 16 },
  labelLarge: { fontSize: 15, fontWeight: '700' as const, lineHeight: 20 },
  labelMedium: { fontSize: 13, fontWeight: '600' as const, lineHeight: 18 },
  labelSmall: { fontSize: 11, fontWeight: '600' as const, lineHeight: 14 },
};

export const Shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 2,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 4,
    elevation: 4,
  },
};

export const WORK_ORDER_STATUS_CONFIG = {
  assigned: { label: 'Assigned', bg: '#EFF6FF', text: '#1D4ED8', border: '#BFDBFE' },
  acknowledged: { label: 'Acknowledged', bg: '#F5F3FF', text: '#6D28D9', border: '#DDD6FE' },
  en_route: { label: 'En Route', bg: '#FFFBEB', text: '#B45309', border: '#FDE68A' },
  on_site: { label: 'On Site', bg: '#FEF3C7', text: '#92400E', border: '#FCD34D' },
  in_progress: { label: 'In Progress', bg: '#FFEDD5', text: '#C2410C', border: '#FED7AA' },
  evidence_uploaded: { label: 'Evidence Uploaded', bg: '#ECFDF5', text: '#047857', border: '#A7F3D0' },
  completed: { label: 'Completed', bg: '#DCFCE7', text: '#15803D', border: '#86EFAC' },
};

export const PRIORITY_CONFIG = {
  critical: { label: 'CRITICAL', color: '#DC2626', bg: '#FEE2E2' },
  high: { label: 'HIGH', color: '#EA580C', bg: '#FFEDD5' },
  medium: { label: 'MEDIUM', color: '#D97706', bg: '#FEF3C7' },
  low: { label: 'LOW', color: '#16A34A', bg: '#DCFCE7' },
};
