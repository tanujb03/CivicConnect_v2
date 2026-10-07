import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { View, Text, StyleSheet, Pressable, Animated } from 'react-native';
import { Colors, Radii, Shadows, Spacing } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastEntry {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextValue {
  show: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue>({
  show: () => {},
});

export const useToast = () => useContext(ToastContext);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);

  const show = useCallback(
    (message: string, type: ToastType = 'info', duration = 3000) => {
      const id = Date.now().toString();
      setToasts((prev) => [...prev, { id, message, type, duration }]);
    },
    []
  );

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <View style={styles.toastContainer} pointerEvents="box-none">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
        ))}
      </View>
    </ToastContext.Provider>
  );
};

const ToastItem: React.FC<{ toast: ToastEntry; onDismiss: () => void }> = ({
  toast,
  onDismiss,
}) => {
  const translateY = useRef(new Animated.Value(-80)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.spring(translateY, {
        toValue: 0,
        friction: 8,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();

    const timer = setTimeout(() => {
      Animated.parallel([
        Animated.timing(opacity, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(translateY, {
          toValue: -80,
          duration: 220,
          useNativeDriver: true,
        }),
      ]).start(() => onDismiss());
    }, toast.duration ?? 3000);

    return () => clearTimeout(timer);
  }, []);

  const getBg = () => {
    switch (toast.type) {
      case 'success':
        return Colors.lime;
      case 'error':
        return Colors.fire;
      case 'warning':
        return Colors.amber;
      default:
        return Colors.ink;
    }
  };

  const getTextColor = () => {
    switch (toast.type) {
      case 'success':
        return Colors.ink;
      case 'error':
        return Colors.onFire;
      case 'warning':
        return Colors.ink;
      default:
        return Colors.surface;
    }
  };

  return (
    <Animated.View
      style={[
        styles.toastWrapper,
        {
          transform: [{ translateY }],
          opacity,
        },
      ]}
      pointerEvents="box-none"
    >
      <Pressable onPress={onDismiss} accessibilityRole="button">
        <HardShadow offset={Shadows.hard} radius={Radii.md}>
          <View style={[styles.toast, { backgroundColor: getBg() }]}>
            <Text style={[styles.toastText, { color: getTextColor() }]}>
              {toast.message}
            </Text>
          </View>
        </HardShadow>
      </Pressable>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  toastContainer: {
    position: 'absolute',
    top: 54,
    left: 0,
    right: 0,
    zIndex: 9999,
    alignItems: 'center',
    paddingHorizontal: Spacing.screenH,
  },
  toastWrapper: {
    width: '100%',
    marginBottom: 8,
  },
  toast: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    minHeight: 48,
    justifyContent: 'center',
  },
  toastText: {
    fontFamily: FontFamily.mono,
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0.3,
  },
});
