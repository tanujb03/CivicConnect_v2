import React from 'react';
import { View, Text, StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { Colors, Radii, Shadows, Spacing, FontSizes, LineHeights } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export interface KpiCardProps {
  value: string | number;
  label: string;
  sub?: string;
  backgroundColor?: string;
  textColor?: string;
  labelColor?: string;
  large?: boolean;
  style?: StyleProp<ViewStyle>;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  value,
  label,
  sub,
  backgroundColor = Colors.surface,
  textColor = Colors.ink,
  labelColor,
  large = false,
  style,
}) => {
  const resolvedLabelColor = labelColor ?? (backgroundColor === Colors.wine ? Colors.onWine : Colors.muted);

  return (
    <HardShadow
      offset={Shadows.card}
      radius={Radii.lg}
      containerStyle={styles.container}
    >
      <View
        style={[
          styles.card,
          {
            backgroundColor,
          },
          style,
        ]}
      >
        <Text
          style={[
            styles.value,
            {
              fontSize: large ? FontSizes.kpiLarge : FontSizes.kpiSmall,
              lineHeight: large ? LineHeights.kpiLarge : LineHeights.kpiSmall,
              color: textColor,
            },
          ]}
        >
          {value}
        </Text>
        <Text style={[styles.label, { color: resolvedLabelColor }]}>
          {label.toUpperCase()}
        </Text>
        {sub ? (
          <Text style={[styles.sub, { color: resolvedLabelColor }]}>{sub}</Text>
        ) : null}
      </View>
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  card: {
    borderRadius: Radii.lg,
    borderWidth: 2,
    borderColor: Colors.ink,
    padding: Spacing.cardInner,
    justifyContent: 'center',
  },
  value: {
    fontFamily: FontFamily.display,
    letterSpacing: -1,
  },
  label: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    letterSpacing: 1.2,
    marginTop: 4,
  },
  sub: {
    fontFamily: FontFamily.sans,
    fontSize: 11,
    marginTop: 2,
  },
});
