import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  StyleProp,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { Colors, Radii, FontSizes, Shadows } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export interface ChipProps {
  label: string;
  backgroundColor?: string;
  textColor?: string;
  borderColor?: string;
  borderWidth?: number;
  icon?: React.ReactNode;
  shadow?: boolean;
  size?: 'sm' | 'md';
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}

export const Chip: React.FC<ChipProps> = ({
  label,
  backgroundColor = Colors.ground,
  textColor = Colors.ink,
  borderColor = Colors.ink,
  borderWidth = 1.5,
  icon,
  shadow = false,
  size = 'md',
  onPress,
  style,
  textStyle,
}) => {
  const isSm = size === 'sm';

  const content = (
    <View
      style={[
        styles.chip,
        {
          backgroundColor,
          borderColor,
          borderWidth,
          paddingVertical: isSm ? 3 : 5,
          paddingHorizontal: isSm ? 8 : 12,
          borderRadius: Radii.full,
        },
        style,
      ]}
    >
      {icon ? <View style={styles.icon}>{icon}</View> : null}
      <Text
        style={[
          styles.text,
          {
            color: textColor,
            fontSize: isSm ? 10 : FontSizes.chip,
          },
          textStyle,
        ]}
      >
        {label}
      </Text>
    </View>
  );

  const interactive = onPress ? (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        pressed ? { transform: [{ scale: 0.96 }] } : undefined,
      ]}
    >
      {content}
    </Pressable>
  ) : (
    content
  );

  if (shadow) {
    return (
      <HardShadow
        offset={{ dx: 2, dy: 2 }}
        radius={Radii.full}
      >
        {interactive}
      </HardShadow>
    );
  }

  return interactive;
};

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
  },
  icon: {
    marginRight: 4,
  },
  text: {
    fontFamily: FontFamily.mono,
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
