// Design tokens — single source of truth for all colour, spacing, radius, shadow, font
// No raw hex ANYWHERE outside this file

export const Colors = {
  // Base
  ground: '#F7F6F0',
  surface: '#FFFFFF',
  ink: '#161616',
  muted: '#5C5A52',
  dot: '#D8D5C6',

  // Brand
  wine: '#580D14',
  onWine: '#F7F6F0',
  fire: '#CF2B09',
  onFire: '#FFFFFF',
  rust: '#A52207',
  rustDeep: '#7C1A06',

  // Accent
  lime: '#C8FF2E',
  amber: '#FFB938',
  limeTint: '#F3FFC4',

  // Heat scale (data visualization only)
  heat1: '#F3FFC4',
  heat2: '#DFF58A',
  heat3: '#FFC27A',
  heat4: '#E8532B',
  heat5: '#580D14',
} as const;

export type ColorKey = keyof typeof Colors;

export const Radii = {
  sm: 8,
  md: 12,
  lg: 18,
  xl: 22,
  full: 9999,
} as const;

// Hard shadows: offset sibling View in ink colour
export const Shadows = {
  hard: { dx: 3, dy: 3 },
  card: { dx: 5, dy: 5 },
  lift: { dx: 8, dy: 9 },
} as const;

export const Spacing = {
  screenH: 20,   // screen horizontal padding
  cardInner: 16, // card inner padding
  cardGap: 14,   // gap between cards
  sectionGap: 24, // gap between sections
} as const;

export const TouchTargets = {
  primary: 56,    // primary buttons, glove-safe
  default: 46,    // standard buttons
  icon: 48,       // icon buttons
} as const;

export const FontSizes = {
  pageTitle: 28,
  cardTitle: 18,
  sectionLabel: 11,
  body: 16,
  small: 13,
  kpiLarge: 56,
  kpiSmall: 36,
  chip: 11,
  script: 24,
} as const;

export const LineHeights = {
  pageTitle: 32,
  cardTitle: 24,
  sectionLabel: 14,
  body: 22,
  small: 18,
  kpiLarge: 56,
  kpiSmall: 36,
} as const;

export const FontWeights = {
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
};

export const LetterSpacing = {
  wide: 1.5,    // section labels
};
