/**
 * F01 — Field Worker Assigned Work
 *
 * Primary workbench for field crews:
 * - Lists work orders dispatched to this crew/worker
 * - Priority & SLA countdown flags
 * - One-tap access to Work Order Detail (F02) & Start Work (F03)
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
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
  WORK_ORDER_STATUS_CONFIG,
  PRIORITY_CONFIG,
} from '../../src/constants/theme';
import { workOrdersApi } from '../../src/api/client';
import type { WorkOrder } from '../../src/types';

export default function AssignedWorkScreen() {
  const router = useRouter();
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'active' | 'in_progress' | 'critical'>('active');

  const fetchOrders = useCallback(async () => {
    try {
      const data = await workOrdersApi.list();
      setWorkOrders(data);
    } catch {}
    finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchOrders();
  };

  const filteredOrders = workOrders.filter(wo => {
    if (filter === 'critical') return wo.priority === 'critical';
    if (filter === 'in_progress') return wo.status === 'in_progress' || wo.status === 'on_site';
    return wo.status !== 'completed';
  });

  const activeCount = workOrders.filter(w => w.status !== 'completed').length;
  const criticalCount = workOrders.filter(w => w.priority === 'critical' && w.status !== 'completed').length;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Top Banner / Worker Header */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View>
            <Text style={styles.workerBadge}>👷 CREW #4 • ZONE EAST</Text>
            <Text style={styles.headerTitle}>Assigned Work Orders</Text>
          </View>
          <View style={styles.kpiPill}>
            <Text style={styles.kpiPillVal}>{activeCount}</Text>
            <Text style={styles.kpiPillLabel}>Active</Text>
          </View>
        </View>

        {criticalCount > 0 && (
          <View style={styles.criticalAlert}>
            <Text style={styles.criticalAlertIcon}>⚠️</Text>
            <Text style={styles.criticalAlertText}>
              {criticalCount} critical SLA work order{criticalCount > 1 ? 's' : ''} require immediate response!
            </Text>
          </View>
        )}

        {/* Filter Pills */}
        <View style={styles.filterRow}>
          <TouchableOpacity
            style={[styles.filterChip, filter === 'active' && styles.filterChipActive]}
            onPress={() => setFilter('active')}
          >
            <Text style={[styles.filterText, filter === 'active' && styles.filterTextActive]}>
              All Active ({activeCount})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.filterChip, filter === 'in_progress' && styles.filterChipActive]}
            onPress={() => setFilter('in_progress')}
          >
            <Text style={[styles.filterText, filter === 'in_progress' && styles.filterTextActive]}>
              In Progress
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.filterChip, filter === 'critical' && styles.filterChipActive]}
            onPress={() => setFilter('critical')}
          >
            <Text style={[styles.filterText, filter === 'critical' && styles.filterTextActive]}>
              🔥 Critical
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Work Orders List */}
      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={Colors.action[600]} />
          <Text style={styles.loadingText}>Loading assigned work orders...</Text>
        </View>
      ) : filteredOrders.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyEmoji}>✅</Text>
          <Text style={styles.emptyTitle}>No Pending Work Orders</Text>
          <Text style={styles.emptyBody}>
            Great job! You have no active work orders matching this filter. Check back when the dispatcher assigns new tasks.
          </Text>
        </View>
      ) : (
        <FlatList
          data={filteredOrders}
          keyExtractor={item => item.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => {
            const statusConfig = WORK_ORDER_STATUS_CONFIG[item.status] ?? WORK_ORDER_STATUS_CONFIG.assigned;
            const priorityConfig = PRIORITY_CONFIG[item.priority] ?? PRIORITY_CONFIG.medium;

            return (
              <TouchableOpacity
                style={styles.card}
                onPress={() => router.push(`/work-order/${item.id}`)}
                activeOpacity={0.8}
              >
                {/* Card Header: Case number & badges */}
                <View style={styles.cardHeader}>
                  <View style={styles.caseNumberWrap}>
                    <Text style={styles.caseNumber}>{item.case_number}</Text>
                    <Text style={styles.departmentName}>{item.department}</Text>
                  </View>
                  <View style={styles.badgesRow}>
                    <View style={[styles.priorityBadge, { backgroundColor: priorityConfig.bg }]}>
                      <Text style={[styles.priorityText, { color: priorityConfig.color }]}>
                        {priorityConfig.label}
                      </Text>
                    </View>
                    <View style={[styles.statusBadge, { backgroundColor: statusConfig.bg, borderColor: statusConfig.border }]}>
                      <Text style={[styles.statusText, { color: statusConfig.text }]}>
                        {statusConfig.label}
                      </Text>
                    </View>
                  </View>
                </View>

                {/* Title & Description */}
                <Text style={styles.cardTitle}>{item.title}</Text>
                {item.description && (
                  <Text style={styles.cardDescription} numberOfLines={2}>
                    {item.description}
                  </Text>
                )}

                {/* Location */}
                <View style={styles.locationRow}>
                  <Text style={styles.locationIcon}>📍</Text>
                  <Text style={styles.locationText} numberOfLines={1}>
                    {item.location.address || `${item.location.lat.toFixed(4)}, ${item.location.lng.toFixed(4)}`}
                  </Text>
                </View>

                {/* Footer: SLA & Action Button */}
                <View style={styles.cardFooter}>
                  <View style={styles.slaIndicator}>
                    <Text style={styles.slaIcon}>⏱️</Text>
                    <Text style={styles.slaText}>
                      SLA: {item.sla_hours ? `${item.sla_hours}h limit` : 'Standard'}
                    </Text>
                  </View>

                  <View style={styles.actionBtn}>
                    <Text style={styles.actionBtnText}>
                      {item.status === 'in_progress' ? 'Resume Work →' : 'View Details →'}
                    </Text>
                  </View>
                </View>
              </TouchableOpacity>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F1F5F9',
  },
  header: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
    gap: Spacing.sm,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  workerBadge: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
    color: Colors.action[700],
    letterSpacing: 0.5,
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.neutral[900],
    marginTop: 2,
  },
  kpiPill: {
    backgroundColor: Colors.neutral[100],
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radii.lg,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.neutral[200],
  },
  kpiPillVal: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.neutral[900],
  },
  kpiPillLabel: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[500],
  },
  criticalAlert: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FCA5A5',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radii.md,
    gap: Spacing.sm,
  },
  criticalAlertIcon: {
    fontSize: 16,
  },
  criticalAlertText: {
    fontSize: Typography.bodySmall.fontSize,
    fontWeight: '700',
    color: '#B91C1C',
    flex: 1,
  },
  filterRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
    marginTop: 2,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[100],
    borderWidth: 1,
    borderColor: Colors.neutral[200],
  },
  filterChipActive: {
    backgroundColor: Colors.action[600],
    borderColor: Colors.action[600],
  },
  filterText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '600',
    color: Colors.neutral[700],
  },
  filterTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
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
    ...Shadows.md,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  caseNumberWrap: {
    gap: 2,
  },
  caseNumber: {
    fontSize: Typography.titleLarge.fontSize,
    fontWeight: '800',
    color: Colors.neutral[900],
  },
  departmentName: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[500],
  },
  badgesRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  priorityBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: Radii.sm,
  },
  priorityText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
  },
  statusBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: Radii.sm,
    borderWidth: 1,
  },
  statusText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
  },
  cardTitle: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  cardDescription: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[600],
    lineHeight: 18,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: Colors.neutral[50],
    padding: Spacing.sm,
    borderRadius: Radii.md,
  },
  locationIcon: {
    fontSize: 14,
  },
  locationText: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[700],
    flex: 1,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: Spacing.xs,
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[100],
  },
  slaIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  slaIcon: {
    fontSize: 14,
  },
  slaText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '600',
    color: Colors.neutral[600],
  },
  actionBtn: {
    backgroundColor: Colors.action[50],
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.action[200],
  },
  actionBtnText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: Colors.action[800],
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
    padding: Spacing.xl,
  },
  loadingText: {
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[600],
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
  emptyBody: {
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[500],
    textAlign: 'center',
    lineHeight: 20,
  },
});
