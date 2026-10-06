/**
 * CivicConnect v2 — Design Tokens
 *
 * Single source of truth for colours, spacing, typography.
 * Matches the admin web portal styling.
 */

export const Colors = {
  // Premium palette tokens from web
  ground: '#F7F6F0',
  surface: '#FFFFFF',
  ink: '#161616',
  muted: '#5C5A52',
  dot: '#D8D5C6',
  wine: '#580D14',
  onWine: '#F7F6F0',
  fire: '#CF2B09',
  onFire: '#FFFFFF',
  rust: '#A52207',
  rustDeep: '#7C1A06',
  lime: '#C8FF2E',
  amber: '#FFB938',
  limeTint: '#F3FFC4',

  // Heat scale
  heat1: '#F3FFC4',
  heat2: '#DFF58A',
  heat3: '#FFC27A',
  heat4: '#E8532B',
  heat5: '#580D14',

  // Legacy mappings for backwards compatibility while migrating
  brand: {
    600: '#161616', // mapping to ink for now
  },

  // Status mapping for cases (using premium tokens where applicable)
  status: {
    submitted: '#5C5A52', // muted
    ai_processing: '#FFB938', // amber
    triaged: '#FFB938', // amber
    assigned: '#FFB938', // amber
    in_progress: '#A52207', // rust
    evidence_uploaded: '#A52207', // rust
    verification_requested: '#C8FF2E', // lime
    resolved: '#C8FF2E', // lime
    reopened: '#CF2B09', // fire
    closed: '#161616', // ink
  } as Record<string, string>,
  
  // Neutral
  neutral: {
    900: '#161616',
    800: '#161616',
    700: '#5C5A52',
    600: '#5C5A52',
    500: '#5C5A52',
    400: '#5C5A52',
    300: '#D8D5C6',
    200: '#D8D5C6',
    100: '#F7F6F0',
    50:  '#F7F6F0',
    white: '#ffffff',
  } as Record<number | string, string>,

  // Semantic
  error:   '#CF2B09',
  warning: '#FFB938',
  success: '#C8FF2E',
  info:    '#161616',
  
  // Background
  background: '#F7F6F0',
  surfaceAlt: '#FFFFFF',
};

// ─── Typography ────────────────────────────────────────────

export const Typography = {
  // Named style objects
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

  // Legacy flat tokens (font sizes)
  xs: 12,
  sm: 13,
  base: 15,
  md: 16,
  lg: 18,
  xl: 20,
  '2xl': 24,
  '3xl': 30,
  '4xl': 36,
  '5xl': 48,

  // Font weights
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
  bold: '700' as const,
  extrabold: '800' as const,
  black: '900' as const,
};

// ─── Spacing ───────────────────────────────────────────────

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,

  0: 0,
  0.5: 2,
  1: 4,
  1.5: 6,
  2: 8,
  2.5: 10,
  3: 12,
  3.5: 14,
  4: 16,
  5: 20,
  6: 24,
  7: 28,
  8: 32,
  10: 40,
  12: 48,
  14: 56,
  16: 64,
};

export const Radii = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  '2xl': 24,
  full: 9999,
} as const;

// Premium hard shadows
export const Shadows = {
  sm: {
    shadowColor: Colors.ink,
    shadowOffset: { width: 1, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 2,
  },
  md: { // card shadow
    shadowColor: Colors.ink,
    shadowOffset: { width: 3, height: 3 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 4,
  },
  lg: { // hard shadow
    shadowColor: Colors.ink,
    shadowOffset: { width: 5, height: 5 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 6,
  },
  civic: {
    shadowColor: Colors.ink,
    shadowOffset: { width: 3, height: 3 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 4,
  },
} as const;

// ─── Constants ──────────────────────────────────────────────

export const CATEGORY_ICONS: Record<string, string> = {
  roads: '🛣️',
  sanitation: '🗑️',
  water: '💧',
  lighting: '💡',
  drainage: '🌊',
  parks: '🌳',
  public_transport: '🚌',
  encroachment: '⛔',
  noise: '🔊',
  other: '⚠️',
};

export const STATUS_LABELS: Record<string, string> = {
  submitted: 'Submitted',
  ai_processing: 'Processing',
  triaged: 'Triaged',
  assigned: 'Assigned',
  in_progress: 'In progress',
  evidence_uploaded: 'Evidence uploaded',
  verification_requested: 'Awaiting verification',
  resolved: 'Resolved',
  reopened: 'Reopened',
  closed: 'Closed',
};

export const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high:     'High',
  medium:   'Medium',
  low:      'Low',
};

export const PRIORITY_COLORS: Record<string, string> = {
  critical: Colors.fire,
  high:     Colors.amber,
  medium:   Colors.amber,
  low:      Colors.ink,
};


export const Layout = {
  bottomNavHeight: 85,
  headerHeight: 60,
  minTouchTarget: 48,
} as const;
