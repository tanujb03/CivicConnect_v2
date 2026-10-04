/**
 * Field Worker — Work History
 *
 * Shows completed tasks, resolution timestamps, and verification states.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import {
  Colors,
  Typography,
  Spacing,
  Radii,
  Shadows,
} from '../../src/constants/theme';
import { workOrdersApi } from '../../src/api/client';
import type { WorkOrder } from '../../src/types';

export default function WorkHistoryScreen() {
  const router = useRouter();
  const [completedOrders, setCompletedOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await workOrdersApi.list();
        setCompletedOrders(data.filter(w => w.status === 'completed'));
      } catch {}
      finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Completed Work Orders</Text>
        <Text style={styles.headerSub}>Resolved tasks awaiting citizen verification or closed</Text>
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="small" color={Colors.brand[600]} />
        </View>
      ) : completedOrders.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyEmoji}>📋</Text>
          <Text style={styles.emptyTitle}>No Completed Orders Yet</Text>
          <Text style={styles.emptySub}>Work orders you mark complete will appear here with verification status.</Text>
        </View>
      ) : (
        <FlatList
          data={completedOrders}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() => router.push(`/work-order/${item.id}`)}
            >
              <View style={styles.cardTop}>
                <Text style={styles.caseNumber}>{item.case_number}</Text>
                <View style={styles.verifiedBadge}>
                  <Text style={styles.verifiedText}>Awaiting Verification</Text>
                </View>
              </View>

              <Text style={styles.cardTitle}>{item.title}</Text>

              {item.work_note && (
                <View style={styles.noteBox}>
                  <Text style={styles.noteLabel}>Resolution Note:</Text>
                  <Text style={styles.noteText}>{item.work_note}</Text>
                </View>
              )}

              <View style={styles.footerRow}>
                <Text style={styles.footerDate}>
                  Completed: {item.completion_time ? new Date(item.completion_time).toLocaleDateString() : 'Today'}
                </Text>
                <Text style={styles.arrowText}>Inspect →</Text>
              </View>
            </TouchableOpacity>
          )}
        />
      )}
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
    gap: 4,
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.neutral[900],
  },
  headerSub: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
  },
  listContent: {
    padding: Spacing.md,
    gap: Spacing.md,
    paddingBottom: Spacing.xxl * 2,
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
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  caseNumber: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.brand[700],
  },
  verifiedBadge: {
    backgroundColor: '#ECFDF5',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: Radii.sm,
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  verifiedText: {
    fontSize: Typography.labelSmall.fontSize,
    color: '#047857',
    fontWeight: '700',
  },
  cardTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '600',
    color: Colors.neutral[800],
  },
  noteBox: {
    backgroundColor: Colors.neutral[50],
    padding: Spacing.sm,
    borderRadius: Radii.md,
    gap: 2,
  },
  noteLabel: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[600],
  },
  noteText: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[700],
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  footerDate: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[400],
  },
  arrowText: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.action[700],
    fontWeight: '700',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xxl,
    gap: Spacing.sm,
  },
  emptyEmoji: {
    fontSize: 48,
  },
  emptyTitle: {
    fontSize: Typography.titleLarge.fontSize,
    fontWeight: '700',
    color: Colors.neutral[800],
  },
  emptySub: {
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[500],
    textAlign: 'center',
  },
});
