import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

// Falls back gracefully if the hook isn't available in older RN versions
export function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (mounted) setReducedMotion(enabled);
      })
      .catch(() => {});

    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      (enabled) => {
        if (mounted) setReducedMotion(enabled);
      }
    );

    return () => {
      mounted = false;
      subscription?.remove?.();
    };
  }, []);

  return reducedMotion;
}
