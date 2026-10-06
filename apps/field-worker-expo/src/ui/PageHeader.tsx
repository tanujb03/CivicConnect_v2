import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Radii, Shadows, Spacing } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  onBack?: () => void;
  rightAction?: React.ReactNode;
  dark?: boolean;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  eyebrow,
  onBack,
  rightAction,
  dark = false,
}) => {
  const textColor = dark ? Colors.onWine : Colors.ink;
  const mutedColor = dark ? Colors.dot : Colors.muted;

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        {onBack ? (
          <HardShadow
            offset={{ dx: 2, dy: 2 }}
            radius={Radii.md}
            containerStyle={styles.backWrapper}
          >
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Go back"
              onPress={onBack}
              style={({ pressed }) => [
                styles.backButton,
                {
                  backgroundColor: dark ? Colors.wine : Colors.surface,
                  transform: pressed ? [{ translateX: 1 }, { translateY: 1 }] : undefined,
                },
              ]}
            >
              <Ionicons
                name="arrow-back"
                size={22}
                color={textColor}
              />
            </Pressable>
          </HardShadow>
        ) : null}

        <View style={styles.titleContainer}>
          {eyebrow ? (
            <Text
              style={[
                styles.eyebrow,
                { color: dark ? Colors.lime : Colors.wine },
              ]}
            >
              {eyebrow}
            </Text>
          ) : null}
          <Text
            style={[styles.title, { color: textColor }]}
            numberOfLines={1}
          >
            {title}
          </Text>
          {subtitle ? (
            <Text
              style={[styles.subtitle, { color: mutedColor }]}
              numberOfLines={1}
            >
              {subtitle}
            </Text>
          ) : null}
        </View>

        {rightAction ? (
          <View style={styles.rightActionWrapper}>{rightAction}</View>
        ) : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: Spacing.screenH,
    paddingTop: 12,
    paddingBottom: 16,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  backWrapper: {
    marginRight: 14,
  },
  backButton: {
    width: 44,
    height: 44,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    justifyContent: 'center',
    alignItems: 'center',
  },
  titleContainer: {
    flex: 1,
    justifyContent: 'center',
  },
  eyebrow: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  title: {
    fontFamily: FontFamily.display,
    fontSize: FontSizes.pageTitle - 4, // 24pt fits better on mobile headers
    letterSpacing: -0.5,
  },
  subtitle: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.small,
    marginTop: 2,
  },
  rightActionWrapper: {
    marginLeft: 12,
  },
});
