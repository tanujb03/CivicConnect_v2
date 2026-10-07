import React from 'react';
import { View, StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { Colors, Radii, Shadows } from '../theme/tokens';

export interface HardShadowProps {
  children: React.ReactNode;
  offset?: { dx: number; dy: number };
  radius?: number;
  color?: string;
  style?: StyleProp<ViewStyle>;
  containerStyle?: StyleProp<ViewStyle>;
}

export const HardShadow: React.FC<HardShadowProps> = ({
  children,
  offset = Shadows.hard,
  radius = Radii.md,
  color = Colors.ink,
  style,
  containerStyle,
}) => {
  return (
    <View style={[styles.container, containerStyle]}>
      <View
        pointerEvents="none"
        style={[
          StyleSheet.absoluteFill,
          {
            backgroundColor: color,
            borderRadius: radius,
            transform: [{ translateX: offset.dx }, { translateY: offset.dy }],
          },
        ]}
      />
      <View style={style}>{children}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'relative',
  },
});
