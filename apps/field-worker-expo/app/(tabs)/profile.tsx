/**
 * Field Worker — Shift & Profile
 *
 * Details active shift, assigned vehicle, crew members,
 * dispatch sync status, and emergency operations hotline.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  Colors,
  Typography,
  Spacing,
  Radii,
  Shadows,
} from '../../src/constants/theme';

export default function WorkerProfileScreen() {
  const [isOnDuty, setIsOnDuty] = useState(true);
  const [offlineSync, setOfflineSync] = useState(true);

  const toggleDuty = (val: boolean) => {
    if (!val) {
      Alert.alert('End Shift', 'Are you sure you want to clock out for this shift?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Clock Out', onPress: () => setIsOnDuty(false) },
      ]);
    } else {
      setIsOnDuty(true);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Shift & Crew Profile</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Worker Badge Card */}
        <View style={styles.workerCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>👷</Text>
          </View>
          <View style={styles.workerInfo}>
            <Text style={styles.workerName}>Ramesh Kumar (ID #FW-842)</Text>
            <Text style={styles.department}>Roads & Civil Works Division</Text>
            <View style={styles.badgeRow}>
              <View style={[styles.statusBadge, isOnDuty ? styles.dutyOn : styles.dutyOff]}>
                <Text style={[styles.statusBadgeText, isOnDuty ? styles.dutyOnText : styles.dutyOffText]}>
                  {isOnDuty ? '● ON ACTIVE SHIFT' : '○ OFF DUTY'}
                </Text>
              </View>
            </View>
          </View>
        </View>

        {/* Shift Duty Toggle */}
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <View>
              <Text style={styles.sectionTitle}>Shift Status</Text>
              <Text style={styles.sectionSub}>Clocked in at 08:00 AM • Zone East, Ward 174</Text>
            </View>
            <Switch
              value={isOnDuty}
              onValueChange={toggleDuty}
              trackColor={{ false: Colors.neutral[300], true: Colors.action[600] }}
            />
          </View>
        </View>

        {/* Crew & Equipment */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Assigned Crew & Vehicle</Text>
          <View style={styles.metaItem}>
            <Text style={styles.metaLabel}>Vehicle:</Text>
            <Text style={styles.metaVal}>KA-01-GA-4412 (Utility Tipper Truck)</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaLabel}>Crew Lead:</Text>
            <Text style={styles.metaVal}>S. Murthy (Foreman)</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaLabel}>Assigned Ward:</Text>
            <Text style={styles.metaVal}>Ward 174 (HSR Layout)</Text>
          </View>
        </View>

        {/* Dispatch & Offline Sync */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Dispatch & Connectivity</Text>
          <View style={styles.rowBetween}>
            <View style={{ flex: 1 }}>
              <Text style={styles.metaLabel}>Offline Queue Sync</Text>
              <Text style={styles.sectionSub}>Auto-sync photo evidence when mobile signal returns</Text>
            </View>
            <Switch
              value={offlineSync}
              onValueChange={setOfflineSync}
              trackColor={{ false: Colors.neutral[300], true: Colors.brand[600] }}
            />
          </View>
        </View>

        {/* Emergency Dispatch Hotline */}
        <TouchableOpacity
          style={styles.emergencyBtn}
          onPress={() => Alert.alert('Municipal Dispatch Control', 'Calling BBMP Central Dispatch: 080-2266-0000')}
        >
          <Text style={styles.emergencyIcon}>📞</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.emergencyTitle}>Municipal Dispatch Control</Text>
            <Text style={styles.emergencySub}>Direct line for heavy machinery, traffic police escort, or gas line hazard</Text>
          </View>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
    backgroundColor: '#FFFFFF',
    padding: Spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.neutral[900],
  },
  scrollContent: {
    padding: Spacing.lg,
    gap: Spacing.lg,
    paddingBottom: Spacing.xxl * 2,
  },
  workerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: Spacing.lg,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.md,
    ...Shadows.sm,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.action[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 28,
  },
  workerInfo: {
    flex: 1,
    gap: 4,
  },
  workerName: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  department: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
  },
  badgeRow: {
    marginTop: 2,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: Radii.sm,
  },
  statusBadgeText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
  },
  dutyOn: {
    backgroundColor: '#DCFCE7',
  },
  dutyOnText: {
    color: '#15803D',
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
  },
  dutyOff: {
    backgroundColor: Colors.neutral[200],
  },
  dutyOffText: {
    color: Colors.neutral[600],
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: Radii.lg,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.sm,
    ...Shadows.sm,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  sectionSub: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
    marginTop: 2,
  },
  metaItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: Spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[100],
  },
  metaLabel: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[600],
  },
  metaVal: {
    fontSize: Typography.bodySmall.fontSize,
    fontWeight: '600',
    color: Colors.neutral[900],
  },
  emergencyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#F87171',
    borderRadius: Radii.lg,
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  emergencyIcon: {
    fontSize: 24,
  },
  emergencyTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: '#991B1B',
  },
  emergencySub: {
    fontSize: Typography.labelSmall.fontSize,
    color: '#B91C1C',
    lineHeight: 16,
    marginTop: 2,
  },
});
