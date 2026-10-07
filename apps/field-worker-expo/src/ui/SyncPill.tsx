import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Radii, Shadows } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';
import { HardShadow } from './HardShadow';

export interface SyncPillProps {
  count: number;
}

export const SyncPill: React.FC<SyncPillProps> = ({ count }) => {
  if (count <= 0) return null;

  return (
    <HardShadow offset={{ dx: 2, dy: 2 }} radius={Radii.full}>
      <View style={styles.pill}>
        <Text style={styles.text}>{count > 99 ? '99+' : count}</Text>
      </View>
    </HardShadow>
  );
};

const styles = StyleSheet.create({
  pill: {
    minWidth: 20,
    height: 20,
    borderRadius: Radii.full,
    backgroundColor: Colors.fire,
    borderWidth: 1.5,
    borderColor: Colors.ink,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  text: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.onFire,
  },
});
