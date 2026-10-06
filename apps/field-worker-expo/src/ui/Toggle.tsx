import React, { useRef, useEffect } from 'react';
import {
  Pressable,
  View,
  StyleSheet,
  StyleProp,
  ViewStyle,
  Animated,
} from 'react-native';
import { Colors, Radii, Shadows } from '../theme/tokens';
import { HardShadow } from './HardShadow';

export interface ToggleProps {
  value: boolean;
  onValueChange: (val: boolean) => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
}

export const Toggle: React.FC<ToggleProps> = ({
  value,
  onValueChange,
  disabled = false,
  style,
}) => {
  const translateX = useRef(new Animated.Value(value ? 20 : 2)).current;

  useEffect(() => {
    Animated.spring(translateX, {
      toValue: value ? 20 : 2,
      friction: 7,
      tension: 60,
      useNativeDriver: true,
    }).start();
  }, [value]);

  const handlePress = () => {
    if (disabled) return;
    onValueChange(!value);
  };

  const trackColor = value
    ? disabled
      ? Colors.limeTint
      : Colors.lime
    : Colors.dot;

  const toggleContent = (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: value, disabled }}
      onPress={handlePress}
      disabled={disabled}
      style={[
        styles.track,
        {
          backgroundColor: trackColor,
          opacity: disabled ? 0.5 : 1,
        },
        style,
      ]}
    >
      <Animated.View
        style={[
          styles.thumb,
          {
            transform: [{ translateX }],
          },
        ]}
      />
    </Pressable>
  );

  return (
    <HardShadow offset={Shadows.hard} radius={Radii.full}>
      {toggleContent}
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  track: {
    width: 48,
    height: 28,
    borderRadius: Radii.full,
    borderWidth: 2,
    borderColor: Colors.ink,
    justifyContent: 'center',
  },
  thumb: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Colors.surface,
    borderWidth: 1.5,
    borderColor: Colors.ink,
  },
});
