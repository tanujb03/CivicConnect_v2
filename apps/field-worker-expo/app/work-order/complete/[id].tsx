/**
 * F05 — Complete Work
 *
 * Final verification and submission step:
 * - Summarizes work completed & evidence attached
 * - Explicitly explains: "Does not close the Civic Case — moves to Citizen Verification"
 * - Clean site sign-off checklist
 * - Dispatches completion to municipal backend
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  Colors,
  Typography,
  Spacing,
  Radii,
  Shadows,
} from '../../../src/constants/theme';
import { workOrdersApi } from '../../../src/api/client';
import type { WorkOrder } from '../../../src/types';

export default function CompleteWorkScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Sign-off checklist
  const [siteCleaned, setSiteCleaned] = useState(false);
  const [hazardConesRemoved, setHazardConesRemoved] = useState(false);
  const [readyForVerification, setReadyForVerification] = useState(false);

  useEffect(() => {
    (async () => {
      if (!id) return;
      try {
        const data = await workOrdersApi.get(id);
        if (data) setOrder(data);
      } catch {}
      finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const allConfirmed = siteCleaned && hazardConesRemoved && readyForVerification;

  const handleCompleteWorkOrder = async () => {
    if (!order) return;
    if (!allConfirmed) {
      Alert.alert('Sign-off Required', 'Please confirm all site restoration items before submitting completion.');
      return;
    }

    setSubmitting(true);
    try {
      await workOrdersApi.complete(order.id, order.work_note);
      Alert.alert(
        'Work Completed!',
        `Work Order ${order.case_number} has been marked COMPLETED.\n\nThe case has been automatically transitioned to CITIZEN VERIFICATION.`,
        [
          {
            text: 'Return to Assigned Tasks',
            onPress: () => router.replace('/(tabs)'),
          },
        ]
      );
    } catch {
      Alert.alert('Error', 'Failed to complete work order. Please check connection.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !order) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.brand[600]} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={styles.backBtnText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Complete Work Order</Text>
        <View style={{ width: 50 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Verification Architecture Banner */}
        <View style={styles.workflowNoticeBanner}>
          <Text style={styles.noticeIcon}>ℹ️</Text>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.noticeTitle}>Civic Verification Protocol</Text>
            <Text style={styles.noticeBody}>
              Completing this work order does not close the Civic Case immediately. Your resolution photos will be sent to the reporting citizen and ward oversight for verification.
            </Text>
          </View>
        </View>

        {/* Work Order Summary Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Resolution Summary</Text>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Work Order:</Text>
            <Text style={styles.summaryVal}>{order.case_number}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Task:</Text>
            <Text style={styles.summaryVal}>{order.title}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Location:</Text>
            <Text style={styles.summaryVal}>{order.location.address || 'HSR Layout'}</Text>
          </View>
          {order.work_note && (
            <View style={styles.noteSection}>
              <Text style={styles.summaryLabel}>Field Work Note:</Text>
              <Text style={styles.noteBody}>{order.work_note}</Text>
            </View>
          )}
          {order.materials_used && (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Materials:</Text>
              <Text style={styles.summaryVal}>{order.materials_used}</Text>
            </View>
          )}
        </View>

        {/* Sign-off checklist */}
        <View style={[styles.card, styles.signoffCard]}>
          <Text style={styles.signoffTitle}>Site Restoration Sign-off</Text>
          <Text style={styles.signoffSub}>Confirm all site safety and cleanliness standards:</Text>

          <TouchableOpacity
            style={styles.checkRow}
            onPress={() => setSiteCleaned(!siteCleaned)}
          >
            <View style={[styles.checkBox, siteCleaned && styles.checkBoxActive]}>
              {siteCleaned && <Text style={styles.checkMark}>✓</Text>}
            </View>
            <View style={styles.checkTextWrap}>
              <Text style={styles.checkTitle}>Site Cleaned & Debris Cleared</Text>
              <Text style={styles.checkDesc}>Construction rubble, excess asphalt, or excavation spoil removed.</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.checkRow}
            onPress={() => setHazardConesRemoved(!hazardConesRemoved)}
          >
            <View style={[styles.checkBox, hazardConesRemoved && styles.checkBoxActive]}>
              {hazardConesRemoved && <Text style={styles.checkMark}>✓</Text>}
            </View>
            <View style={styles.checkTextWrap}>
              <Text style={styles.checkTitle}>Traffic Safety & Cones Demobilized</Text>
              <Text style={styles.checkDesc}>All caution tape, barricades, and cones retrieved; normal traffic restored.</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.checkRow}
            onPress={() => setReadyForVerification(!readyForVerification)}
          >
            <View style={[styles.checkBox, readyForVerification && styles.checkBoxActive]}>
              {readyForVerification && <Text style={styles.checkMark}>✓</Text>}
            </View>
            <View style={styles.checkTextWrap}>
              <Text style={styles.checkTitle}>Certified Ready for Citizen Inspection</Text>
              <Text style={styles.checkDesc}>Repair meets municipal technical standards and is safe for public use.</Text>
            </View>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Completion Button */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={[styles.completeBtn, !allConfirmed && styles.completeBtnDisabled]}
          onPress={handleCompleteWorkOrder}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.completeBtnText}>
              {allConfirmed ? '✅ Submit & Dispatch to Verification' : 'Confirm Restoration Items Above'}
            </Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
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
  backBtn: {
    padding: Spacing.sm,
  },
  backBtnText: {
    fontSize: Typography.bodyLarge.fontSize,
    color: Colors.action[700],
    fontWeight: '700',
  },
  headerTitle: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  scrollContent: {
    padding: Spacing.md,
    gap: Spacing.md,
    paddingBottom: 110,
  },
  workflowNoticeBanner: {
    flexDirection: 'row',
    backgroundColor: '#EFF6FF',
    padding: Spacing.md,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: '#BFDBFE',
    gap: Spacing.md,
    alignItems: 'center',
  },
  noticeIcon: {
    fontSize: 24,
  },
  noticeTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: '#1E40AF',
  },
  noticeBody: {
    fontSize: Typography.bodySmall.fontSize,
    color: '#1E3A8A',
    lineHeight: 18,
  },
  card: {
    backgroundColor: '#FFFFFF',
    padding: Spacing.lg,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.sm,
    ...Shadows.sm,
  },
  cardTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
    marginBottom: Spacing.xs,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 3,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[100],
  },
  summaryLabel: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
    fontWeight: '600',
  },
  summaryVal: {
    fontSize: Typography.bodySmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[800],
    flex: 1,
    textAlign: 'right',
  },
  noteSection: {
    paddingVertical: Spacing.xs,
    gap: 2,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[100],
  },
  noteBody: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[700],
    lineHeight: 18,
  },
  signoffCard: {
    backgroundColor: '#F0FDF4',
    borderColor: '#BBF7D0',
  },
  signoffTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '800',
    color: '#166534',
  },
  signoffSub: {
    fontSize: Typography.bodySmall.fontSize,
    color: '#15803D',
    marginBottom: Spacing.xs,
  },
  checkRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    paddingVertical: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: '#DCFCE7',
  },
  checkBox: {
    width: 24,
    height: 24,
    borderRadius: Radii.sm,
    borderWidth: 2,
    borderColor: '#15803D',
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  checkBoxActive: {
    backgroundColor: '#15803D',
  },
  checkMark: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
  },
  checkTextWrap: {
    flex: 1,
    gap: 2,
  },
  checkTitle: {
    fontSize: Typography.bodyMedium.fontSize,
    fontWeight: '700',
    color: '#14532D',
  },
  checkDesc: {
    fontSize: Typography.bodySmall.fontSize,
    color: '#166534',
    lineHeight: 18,
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
  completeBtn: {
    backgroundColor: Colors.brand[700],
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    alignItems: 'center',
  },
  completeBtnDisabled: {
    backgroundColor: Colors.neutral[300],
  },
  completeBtnText: {
    fontSize: Typography.labelLarge.fontSize,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
