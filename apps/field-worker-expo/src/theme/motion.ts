// Motion constants used across the app
// When reduced motion is active, use duration 0 and skip spring animations

export const Motion = {
  // Durations (ms)
  fast: 150,
  normal: 240,
  slow: 380,

  // Spring configs for Animated.spring
  spring: {
    tension: 120,
    friction: 8,
  },

  // Easing names (for reference)
  easing: {
    standard: 'ease-in-out',
    enter: 'ease-out',
    exit: 'ease-in',
  },
} as const;
