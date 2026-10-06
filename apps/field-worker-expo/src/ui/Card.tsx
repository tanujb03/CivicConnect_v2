import React from 'react';
import {
  View,
  StyleSheet,
  Pressable,
  StyleProp,
  ViewStyle,
} from 'react-native';
import { Colors, Radii, Shadows, Spacing } from '../theme/tokens';
import { HardShadow } from './HardShadow';

export type CardShadowType = 'none' | 'hard' | 'card' | 'lift';

export interface CardProps {
  children: React.ReactNode;
  shadow?: CardShadowType;
  backgroundColor?: string;
  borderColor?: string;
  borderWidth?: number;
  radius?: number;
  padding?: number;
  style?: StyleProp<ViewStyle>;
  containerStyle?: StyleProp<ViewStyle>;
  onPress?: () => void;
  accessibilityLabel?: string;
}

export const Card: React.FC<CardProps> = ({
  children,
  shadow = 'card',
  backgroundColor = Colors.surface,
  borderColor = Colors.ink,
  borderWidth = 2,
  radius = Radii.lg,
  padding = Spacing.cardInner,
  style,
  containerStyle,
  onPress,
  accessibilityLabel,
}) => {
  const cardContent = (
    <View
      style={[
        styles.cardBase,
        {
          backgroundColor,
          borderColor,
          borderWidth,
          borderRadius: radius,
          padding,
        },
        style,
      ]}
    >
      {children}
    </View>
  );

  const interactiveWrapper = onPress ? (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={onPress}
      style={({ pressed }) => [
        pressed && shadow !== 'none'
          ? { transform: [{ translateX: 2 }, { translateY: 2 }] }
          : undefined,
      ]}
    >
      {cardContent}
    </Pressable>
  ) : (
    cardContent
  );

  if (shadow === 'none') {
    return <View style={containerStyle}>{interactiveWrapper}</View>;
  }

  const offset =
    shadow === 'hard'
      ? Shadows.hard
      : shadow === 'lift'
      ? Shadows.lift
      : Shadows.card;

  return (
    <HardShadow
      offset={offset}
      radius={radius}
      containerStyle={containerStyle}
    >
      {interactiveWrapper}
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  cardBase: {
    overflow: 'hidden',
  },
});
