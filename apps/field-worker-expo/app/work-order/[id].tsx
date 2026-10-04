/**
 * F02 — Work Order Detail
 *
 * Displays:
 * - Location (Address, Ward, GPS coordinates)
 * - Issue summary & Department
 * - Original Citizen Evidence gallery
 * - Priority & SLA Countdown
 * - Supervisor / Dispatch Instructions
 * - Contextual primary action (Start Work -> Upload Evidence -> Complete Work)
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
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

export default function WorkOrderDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchOrder = useCallback(async () => {
    if (!id) return;
    try {
      const data = await workOrdersApi.get(id);
      if (data) setOrder(data);
    } catch {}
    finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const openNavigation = () => {
    if (!order?.location) return;
    const { lat, lng } = order.location;
    const label = encodeURIComponent(order.title);
    const url = Platform.select({
      ios: `maps:0,0?q=${label}@${lat},${lng}`,
      android: `geo:0,0?q=${lat},${lng}(${label})`,
      default: `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`,
    });
    if (url) Linking.openURL(url);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.action[600]} />
        <Text style={styles.loadingText}>Loading work order details...</Text>
      </SafeAreaView>
    );
  }

  if (!order) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.errorTitle}>Work Order Not Found</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={styles.backBtnText}>‹ Back to Assigned Tasks</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const statusConfig = WORK_ORDER_STATUS_CONFIG[order.status] ?? WORK_ORDER_STATUS_CONFIG.assigned;
  const priorityConfig = PRIORITY_CONFIG[order.priority] ?? PRIORITY_CONFIG.medium;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Top Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBackBtn} onPress={() => router.back()}>
          <Text style={styles.headerBackText}>‹ Tasks</Text>
        </TouchableOpacity>
        <View style={styles.headerTitleWrap}>
          <Text style={styles.headerCaseNumber}>{order.case_number}</Text>
          <Text style={styles.headerSubtitle}>WORK ORDER</Text>
        </View>
        <View style={{ width: 50 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Status & Priority Banner */}
        <View style={styles.bannerRow}>
          <View style={[styles.priorityBadge, { backgroundColor: priorityConfig.bg }]}>
            <Text style={[styles.priorityText, { color: priorityConfig.color }]}>
              {priorityConfig.label} PRIORITY
            </Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: statusConfig.bg, borderColor: statusConfig.border }]}>
            <Text style={[styles.statusText, { color: statusConfig.text }]}>
              {statusConfig.label}
            </Text>
          </View>
        </View>

        {/* Title & Department */}
        <View style={styles.sectionCard}>
          <Text style={styles.orderTitle}>{order.title}</Text>
          <Text style={styles.departmentText}>🏢 {order.department}</Text>
          {order.description && (
            <Text style={styles.descriptionText}>{order.description}</Text>
          )}
        </View>

        {/* Location & Navigation */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionHeading}>Site Location</Text>
            <TouchableOpacity style={styles.navBtn} onPress={openNavigation}>
              <Text style={styles.navBtnText}>🧭 Open GPS</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.addressText}>
            {order.location.address || 'Field Site Coordinates'}
          </Text>
          {order.location.landmark && (
            <Text style={styles.landmarkText}>Landmark: {order.location.landmark}</Text>
          )}
          <Text style={styles.coordText}>
            GPS: {order.location.lat.toFixed(5)}, {order.location.lng.toFixed(5)} • {order.location.ward || 'Zone East'}
          </Text>
        </View>

        {/* Dispatch Instructions */}
        <View style={[styles.sectionCard, styles.instructionsCard]}>
          <Text style={styles.instructionHeading}>⚠️ Field Instructions & Task Scope</Text>
          <Text style={styles.instructionBody}>
            {order.instructions || 'Inspect physical site, secure safety perimeter, repair defect, and photograph completed resolution.'}
          </Text>

          {order.required_evidence && order.required_evidence.length > 0 && (
            <View style={styles.evidenceReqWrap}>
              <Text style={styles.evidenceReqTitle}>Mandatory Completion Evidence:</Text>
              {order.required_evidence.map((req, idx) => (
                <Text key={idx} style={styles.evidenceReqItem}>
                  ✓ {req}
                </Text>
              ))}
            </View>
          )}
        </View>

        {/* Original Citizen Evidence Gallery */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeading}>Original Citizen Evidence</Text>
          {order.original_evidence.length === 0 ? (
            <Text style={styles.noEvidenceText}>No original photo attached by citizen reporter.</Text>
          ) : (
            <View style={styles.gallery}>
              {order.original_evidence.map(ev => (
                <View key={ev.id} style={styles.evidenceBox}>
                  <Image source={{ uri: ev.url }} style={styles.evidenceImg} />
                  <View style={styles.evidenceOverlay}>
                    <Text style={styles.evidenceSourceBadge}>CITIZEN REPORT</Text>
                    {ev.caption && <Text style={styles.evidenceCaption}>{ev.caption}</Text>}
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* SLA & Time Tracking */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionHeading}>SLA & Time Targets</Text>
          <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>Assigned At:</Text>
            <Text style={styles.metaValue}>{new Date(order.assigned_at).toLocaleString()}</Text>
          </View>
          {order.start_time && (
            <View style={styles.metaRow}>
              <Text style={styles.metaLabel}>Work Commenced:</Text>
              <Text style={styles.metaValue}>{new Date(order.start_time).toLocaleString()}</Text>
            </View>
          )}
          {order.completion_time && (
            <View style={styles.metaRow}>
              <Text style={styles.metaLabel}>Work Finished:</Text>
              <Text style={styles.metaValue}>{new Date(order.completion_time).toLocaleString()}</Text>
            </View>
          )}
          {order.deadline && (
            <View style={styles.metaRow}>
              <Text style={styles.metaLabel}>SLA Deadline:</Text>
              <Text style={[styles.metaValue, { color: Colors.error[700], fontWeight: '700' }]}>
                {new Date(order.deadline).toLocaleString()}
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Floating Bottom Workflow Action */}
      <View style={styles.bottomBar}>
        {order.status === 'assigned' || order.status === 'acknowledged' ? (
          <TouchableOpacity
            style={styles.primaryActionBtn}
            onPress={() => router.push(`/work-order/start/${order.id}`)}
          >
            <Text style={styles.primaryActionText}>🚀 Start Work at Site (F03)</Text>
          </TouchableOpacity>
        ) : order.status === 'in_progress' || order.status === 'on_site' ? (
          <TouchableOpacity
            style={[styles.primaryActionBtn, styles.evidenceBtn]}
            onPress={() => router.push(`/work-order/evidence/${order.id}`)}
          >
            <Text style={styles.primaryActionText}>📸 Upload Resolution Evidence (F04)</Text>
          </TouchableOpacity>
        ) : order.status === 'evidence_uploaded' ? (
          <TouchableOpacity
            style={[styles.primaryActionBtn, styles.completeBtn]}
            onPress={() => router.push(`/work-order/complete/${order.id}`)}
          >
            <Text style={styles.primaryActionText}>✅ Finalize & Complete Work (F05)</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.completedNotice}>
            <Text style={styles.completedNoticeText}>
              ✓ Work Order Completed • Dispatched to Citizen Verification
            </Text>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F1F5F9',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
  },
  headerBackBtn: {
    padding: Spacing.sm,
  },
  headerBackText: {
    fontSize: Typography.bodyLarge.fontSize,
    color: Colors.action[700],
    fontWeight: '700',
  },
  headerTitleWrap: {
    alignItems: 'center',
  },
  headerCaseNumber: {
    fontSize: Typography.titleLarge.fontSize,
    fontWeight: '800',
    color: Colors.neutral[900],
  },
  headerSubtitle: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[400],
    letterSpacing: 0.5,
  },
  scrollContent: {
    padding: Spacing.md,
    gap: Spacing.md,
    paddingBottom: 110,
  },
  bannerRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  priorityBadge: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 4,
    borderRadius: Radii.sm,
  },
  priorityText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
  },
  statusBadge: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 4,
    borderRadius: Radii.sm,
    borderWidth: 1,
  },
  statusText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
  },
  sectionCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: Radii.lg,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.sm,
    ...Shadows.sm,
  },
  orderTitle: {
    fontSize: Typography.titleLarge.fontSize,
    fontWeight: '800',
    color: Colors.neutral[900],
  },
  departmentText: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.action[700],
    fontWeight: '600',
  },
  descriptionText: {
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[700],
    lineHeight: 22,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionHeading: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  navBtn: {
    backgroundColor: Colors.info[50],
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: '#BAE6FD',
  },
  navBtnText: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.info[700],
    fontWeight: '700',
  },
  addressText: {
    fontSize: Typography.bodyMedium.fontSize,
    fontWeight: '600',
    color: Colors.neutral[800],
  },
  landmarkText: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[600],
  },
  coordText: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[400],
    marginTop: 2,
  },
  instructionsCard: {
    backgroundColor: '#FFFBEB',
    borderColor: '#FCD34D',
  },
  instructionHeading: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '800',
    color: '#92400E',
  },
  instructionBody: {
    fontSize: Typography.bodyMedium.fontSize,
    color: '#78350F',
    lineHeight: 20,
  },
  evidenceReqWrap: {
    marginTop: Spacing.xs,
    gap: 4,
    borderTopWidth: 1,
    borderTopColor: '#FDE68A',
    paddingTop: Spacing.sm,
  },
  evidenceReqTitle: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: '#B45309',
  },
  evidenceReqItem: {
    fontSize: Typography.bodySmall.fontSize,
    color: '#92400E',
  },
  gallery: {
    gap: Spacing.sm,
  },
  evidenceBox: {
    borderRadius: Radii.md,
    overflow: 'hidden',
    position: 'relative',
    height: 180,
  },
  evidenceImg: {
    width: '100%',
    height: '100%',
    backgroundColor: Colors.neutral[200],
  },
  evidenceOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#000000AA',
    padding: Spacing.sm,
  },
  evidenceSourceBadge: {
    color: '#38BDF8',
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
  },
  evidenceCaption: {
    color: '#FFFFFF',
    fontSize: Typography.bodySmall.fontSize,
    marginTop: 2,
  },
  noEvidenceText: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
    fontStyle: 'italic',
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 2,
  },
  metaLabel: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
  },
  metaValue: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[800],
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[200],
    ...Shadows.md,
  },
  primaryActionBtn: {
    backgroundColor: Colors.action[600],
    borderRadius: Radii.md,
    paddingVertical: Spacing.md,
    alignItems: 'center',
  },
  evidenceBtn: {
    backgroundColor: '#0284C7',
  },
  completeBtn: {
    backgroundColor: Colors.brand[700],
  },
  primaryActionText: {
    fontSize: Typography.labelLarge.fontSize,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  completedNotice: {
    backgroundColor: '#DCFCE7',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: Radii.md,
    alignItems: 'center',
  },
  completedNoticeText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: '#15803D',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
  },
  loadingText: {
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[600],
  },
  errorTitle: {
    fontSize: Typography.titleLarge.fontSize,
    fontWeight: '700',
    color: Colors.neutral[800],
  },
  backBtn: {
    padding: Spacing.md,
  },
  backBtnText: {
    color: Colors.action[700],
    fontSize: Typography.bodyMedium.fontSize,
    fontWeight: '700',
  },
});
