/**
 * CivicConnect v2 — Design Tokens
 *
 * Single source of truth for colours, spacing, typography.
 * Use these constants in StyleSheet.create() — do not hardcode values in components.
 */

export const Colors = {
  // Brand — civic green palette
  brand: {
    900: '#0a3212',
    800: '#0d4a1a',
    700: '#1a6b2e',
    600: '#1a7a2e',
    500: '#239a3e',
    400: '#27a94a',
    300: '#4dbf6a',
    200: '#6cc77a',
    100: '#b3e5bb',
    50:  '#e8f8ec',
  } as Record<number | string, string>,

  // Status colours
  status: {
    submitted:        '#3b82f6',
    ai_processing:    '#8b5cf6',
    triaged:          '#f59e0b',
    assigned:         '#f59e0b',
    in_progress:      '#f97316',
    evidence_uploaded: '#06b6d4',
    verification_requested: '#ec4899',
    resolved:         '#10b981',
    reopened:         '#ef4444',
    closed:           '#6b7280',
  } as Record<string, string>,

  // Priority colours
  priority: {
    critical: '#dc2626',
    high:     '#ea580c',
    medium:   '#d97706',
    low:      '#16a34a',
  } as Record<string, string>,

  // Category colours
  category: {
    roads:           '#ef4444',
    sanitation:      '#f97316',
    water:           '#3b82f6',
    lighting:        '#eab308',
    drainage:        '#06b6d4',
    parks:           '#22c55e',
    public_transport: '#a855f7',
    encroachment:    '#f43f5e',
    noise:           '#6366f1',
    other:           '#6b7280',
  } as Record<string, string>,

  // Neutral
  neutral: {
    900: '#111827',
    800: '#1f2937',
    700: '#374151',
    600: '#4b5563',
    500: '#6b7280',
    400: '#9ca3af',
    300: '#d1d5db',
    200: '#e5e7eb',
    100: '#f3f4f6',
    50:  '#f9fafb',
    white: '#ffffff',
  } as Record<number | string, string>,

  // Semantic
  error:   '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
  info:    '#3b82f6',

  // Background
  background: '#f0faf2',
  surface:    '#ffffff',
  surfaceAlt: '#f9fafb',
};

// ─── Typography ────────────────────────────────────────────
// Named style objects used by components as Typography.titleLarge.fontSize etc.
// Also retains flat legacy keys for backward-compat (Typography.xs, Typography.bold …).

export const Typography = {
  // ── Named style objects ──────────────────────────────────
  headlineSmall:  { fontSize: 24, fontWeight: '700' as const },
  titleLarge:     { fontSize: 20, fontWeight: '700' as const },
  titleMedium:    { fontSize: 16, fontWeight: '600' as const },
  titleSmall:     { fontSize: 14, fontWeight: '600' as const },
  bodyLarge:      { fontSize: 18, fontWeight: '400' as const },
  bodyMedium:     { fontSize: 15, fontWeight: '400' as const },
  bodySmall:      { fontSize: 13, fontWeight: '400' as const },
  labelLarge:     { fontSize: 16, fontWeight: '600' as const },
  labelMedium:    { fontSize: 14, fontWeight: '500' as const },
  labelSmall:     { fontSize: 12, fontWeight: '500' as const },

  // ── Legacy flat tokens (font sizes) ──────────────────────
  xs:   12,
  sm:   13,
  base: 15,
  md:   16,
  lg:   18,
  xl:   20,
  '2xl': 24,
  '3xl': 30,

  // Font weights (React Native uses string)
  regular:    '400' as const,
  medium:     '500' as const,
  semibold:   '600' as const,
  bold:       '700' as const,
  extrabold:  '800' as const,

  // Line heights
  tight:  1.25,
  normal: 1.5,
  relaxed: 1.75,
};

// ─── Spacing ───────────────────────────────────────────────
// Named tokens (xs … xxl) used in StyleSheet + numeric keys for granular control.

export const Spacing = {
  // Named tokens
  xs:  4,
  sm:  8,
  md:  16,
  lg:  24,
  xl:  32,
  xxl: 48,

  // Numeric scale
  0:   0,
  0.5: 2,
  1:   4,
  1.5: 6,
  2:   8,
  2.5: 10,
  3:   12,
  3.5: 14,
  4:   16,
  5:   20,
  6:   24,
  7:   28,
  8:   32,
  10:  40,
  12:  48,
  14:  56,
  16:  64,
};

export const Radii = {
  sm:   8,
  md:   12,
  lg:   16,
  xl:   20,
  '2xl': 24,
  full: 9999,
} as const;

export const Shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.10,
    shadowRadius: 16,
    elevation: 6,
  },
  civic: {
    shadowColor: '#1a7a2e',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.20,
    shadowRadius: 12,
    elevation: 4,
  },
} as const;

// ─── Category labels ──────────────────────────────────────

export const CATEGORY_LABELS: Record<string, string> = {
  roads:            'Roads',
  sanitation:       'Sanitation',
  water:            'Water',
  lighting:         'Lighting',
  drainage:         'Drainage',
  parks:            'Parks',
  public_transport: 'Public Transport',
  encroachment:     'Encroachment',
  noise:            'Noise',
  other:            'Other',
};

export const CATEGORY_ICONS: Record<string, string> = {
  roads:            '🛣️',
  sanitation:       '🗑️',
  water:            '💧',
  lighting:         '💡',
  drainage:         '🌊',
  parks:            '🌳',
  public_transport: '🚌',
  encroachment:     '⛔',
  noise:            '🔊',
  other:            '⚠️',
};

// ─── Status labels ────────────────────────────────────────

export const STATUS_LABELS: Record<string, string> = {
  submitted:             'Submitted',
  ai_processing:         'Processing',
  triaged:               'Triaged',
  assigned:              'Assigned',
  in_progress:           'In Progress',
  evidence_uploaded:     'Evidence Uploaded',
  verification_requested: 'Awaiting Verification',
  resolved:              'Resolved',
  reopened:              'Reopened',
  closed:                'Closed',
};

// ─── Priority labels & colours ────────────────────────────

export const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high:     'High',
  medium:   'Medium',
  low:      'Low',
};

/** Alias for Colors.priority — importable as PRIORITY_COLORS */
export const PRIORITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high:     '#ea580c',
  medium:   '#d97706',
  low:      '#16a34a',
};

// ─── Layout constants ──────────────────────────────────────

export const Layout = {
  bottomNavHeight: 70,
  headerHeight:    60,
  minTouchTarget:  44,
} as const;
