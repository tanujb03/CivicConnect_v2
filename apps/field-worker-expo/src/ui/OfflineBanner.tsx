import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '../theme/tokens';
import { FontFamily } from '../theme/fonts';

export interface OfflineBannerProps {
  onPress?: () => void;
  pendingCount?: number;
}

export const OfflineBanner: React.FC<OfflineBannerProps> = ({
  onPress,
  pendingCount = 0,
}) => {
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={styles.banner}
      accessibilityRole="alert"
      accessibilityLabel={`Offline. ${pendingCount} item${pendingCount === 1 ? '' : 's'} pending sync.`}
    >
      <Ionicons name="cloud-offline-outline" size={16} color={Colors.onFire} />
      <Text style={styles.text}>
        OFFLINE
        {pendingCount > 0 ? ` — ${pendingCount} PENDING` : ''}
      </Text>
      {onPress ? (
        <Ionicons name="chevron-forward" size={14} color={Colors.onFire} />
      ) : null}
    </Pressable>
  );
};

const styles = StyleSheet.create({
  banner: {
    backgroundColor: Colors.fire,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: Spacing.screenH,
    gap: 6,
  },
  text: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    fontWeight: '500',
    color: Colors.onFire,
    letterSpacing: 1,
    flex: 1,
  },
});
