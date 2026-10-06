import React from 'react';
import {
  Pressable,
  Text,
  StyleSheet,
  ActivityIndicator,
  View,
  StyleProp,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { Colors, Radii, Shadows, TouchTargets } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export type ButtonVariant = 'primary' | 'wine' | 'fire' | 'secondary' | 'ghost';
export type ButtonSize = 'primary' | 'default' | 'sm';

export interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  accessibilityLabel?: string;
  testID?: string;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  size = 'primary',
  disabled = false,
  loading = false,
  leftIcon,
  rightIcon,
  style,
  textStyle,
  accessibilityLabel,
  testID,
}) => {
  const isGhost = variant === 'ghost';
  const height =
    size === 'primary'
      ? TouchTargets.primary
      : size === 'default'
      ? TouchTargets.default
      : 38;

  const getBgColor = () => {
    if (disabled) return Colors.dot;
    switch (variant) {
      case 'primary':
        return Colors.lime;
      case 'wine':
        return Colors.wine;
      case 'fire':
        return Colors.fire;
      case 'secondary':
        return Colors.surface;
      case 'ghost':
        return 'transparent';
      default:
        return Colors.lime;
    }
  };

  const getTextColor = () => {
    if (disabled) return Colors.muted;
    switch (variant) {
      case 'primary':
        return Colors.ink;
      case 'wine':
        return Colors.onWine;
      case 'fire':
        return Colors.onFire;
      case 'secondary':
        return Colors.ink;
      case 'ghost':
        return Colors.ink;
      default:
        return Colors.ink;
    }
  };

  const content = (
    <Pressable
      testID={testID}
      accessibilityLabel={accessibilityLabel || title}
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading, busy: loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.buttonBase,
        {
          height,
          backgroundColor: getBgColor(),
          borderColor: isGhost ? 'transparent' : Colors.ink,
          borderWidth: isGhost ? 0 : 2,
          borderRadius: Radii.md,
          transform: pressed && !isGhost ? [{ translateX: 1.5 }, { translateY: 1.5 }] : [],
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={getTextColor()}
        />
      ) : (
        <View style={styles.contentRow}>
          {leftIcon ? <View style={styles.iconWrapper}>{leftIcon}</View> : null}
          <Text
            style={[
              styles.text,
              {
                color: getTextColor(),
                fontSize: size === 'sm' ? 14 : 16,
              },
              textStyle,
            ]}
          >
            {title}
          </Text>
          {rightIcon ? <View style={styles.iconWrapper}>{rightIcon}</View> : null}
        </View>
      )}
    </Pressable>
  );

  if (isGhost || disabled) {
    return <View style={styles.container}>{content}</View>;
  }

  return (
    <HardShadow
      offset={Shadows.hard}
      radius={Radii.md}
      containerStyle={styles.container}
    >
      {content}
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  buttonBase: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  contentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconWrapper: {
    marginHorizontal: 6,
  },
  text: {
    fontFamily: FontFamily.sansSemiBold,
    fontWeight: '600',
    textAlign: 'center',
  },
});
