import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Alert,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Radii, Shadows, Spacing } from '../../src/theme/tokens';
import { FontFamily } from '../../src/theme/fonts';
import {
  Card,
  PageHeader,
  PriorityChip,
  StatusChip,
  SlaChip,
  Button,
  StateView,
  HardShadow,
  useToast,
} from '../../src/ui';
import { apiClient } from '../../src/api/client';

function InfoRow({ icon, label, value, onPress }: {
  icon: string;
  label: string;
  value: string;
  onPress?: () => void;
}) {
  const content = (
    <View style={styles.infoRow}>
      <Ionicons name={icon as any} size={16} color={Colors.wine} />
      <View style={styles.infoContent}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={[styles.infoValue, onPress && styles.infoLink]}>{value}</Text>
      </View>
      {onPress ? <Ionicons name="chevron-forward" size={14} color={Colors.muted} /> : null}
    </View>
  );

  if (onPress) {
    return (
      <Pressable onPress={onPress} accessibilityRole="link">
        {content}
      </Pressable>
    );
  }
  return content;
}

export default function WorkOrderDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { show } = useToast();
  const queryClient = useQueryClient();

  const { data: workOrder, isLoading, isError } = useQuery({
    queryKey: ['workOrder', id],
    queryFn: () => apiClient.getWorkOrder(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: (status: 'IN_PROGRESS' | 'DONE' | 'CANCELLED') =>
      apiClient.updateWorkOrder(id!, { status }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['workOrder', id], updated);
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      queryClient.invalidateQueries({ queryKey: ['kpi'] });
      show('Status updated', 'success');
    },
    onError: () => show('Failed to update status', 'error'),
  });

  const handleCallCitizen = () => {
    if (workOrder?.citizenPhone) {
      Linking.openURL(`tel:${workOrder.citizenPhone}`).catch(() =>
        show('Could not open dialer', 'error')
      );
    }
  };

  const handleOpenMaps = () => {
    if (workOrder?.lat && workOrder?.lng) {
      const url = `https://maps.google.com/?q=${workOrder.lat},${workOrder.lng}`;
      Linking.openURL(url).catch(() => show('Could not open Maps', 'error'));
    } else {
      const url = `https://maps.google.com/?q=${encodeURIComponent(workOrder?.address ?? '')}`;
      Linking.openURL(url);
    }
  };

  const handleQuickAccept = () => {
    if (workOrder?.status !== 'OPEN') return;
    Alert.alert(
      'Accept Work Order',
      'Mark this work order as In Progress?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Accept',
          onPress: () => mutation.mutate('IN_PROGRESS'),
        },
      ]
    );
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="loading" title="Loading work order..." />
      </SafeAreaView>
    );
  }

  if (isError || !workOrder) {
    return (
      <SafeAreaView style={styles.root}>
        <PageHeader title="Work Order" onBack={() => router.back()} />
        <StateView
          variant="error"
          title="Not found"
          message="This work order could not be loaded"
          actionLabel="Go Back"
          onAction={() => router.back()}
        />
      </SafeAreaView>
    );
  }

  const isDone = workOrder.status === 'DONE' || workOrder.status === 'CANCELLED';

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <PageHeader
          title={workOrder.caseId}
          eyebrow={`WARD ${workOrder.ward}`}
          subtitle={`Last updated ${new Date(workOrder.updatedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}`}
          onBack={() => router.back()}
        />

        {/* Status + chips */}
        <View style={styles.chipRow}>
          <PriorityChip priority={workOrder.priority} />
          <StatusChip status={workOrder.status} />
          <SlaChip deadline={workOrder.slaDeadline} />
        </View>

        {/* Title */}
        <View style={styles.section}>
          <Text style={styles.workTitle}>{workOrder.title}</Text>
        </View>

        {/* Description */}
        <Card shadow="hard" containerStyle={styles.cardMargin}>
          <Text style={styles.sectionLabel}>DESCRIPTION</Text>
          <Text style={styles.description}>{workOrder.description}</Text>
        </Card>

        {/* Location & Citizen */}
        <Card shadow="hard" containerStyle={styles.cardMargin}>
          <Text style={styles.sectionLabel}>DETAILS</Text>

          <InfoRow
            icon="location-outline"
            label="Address"
            value={workOrder.address}
            onPress={handleOpenMaps}
          />
          <View style={styles.rowDivider} />

          <InfoRow
            icon="grid-outline"
            label="Category"
            value={workOrder.category}
          />
          <View style={styles.rowDivider} />

          <InfoRow
            icon="calendar-outline"
            label="Created"
            value={new Date(workOrder.createdAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
          />

          {workOrder.citizenName ? (
            <>
              <View style={styles.rowDivider} />
              <InfoRow
                icon="person-outline"
                label="Reported by"
                value={workOrder.citizenName}
              />
            </>
          ) : null}

          {workOrder.citizenPhone ? (
            <>
              <View style={styles.rowDivider} />
              <InfoRow
                icon="call-outline"
                label="Citizen phone"
                value={workOrder.citizenPhone}
                onPress={handleCallCitizen}
              />
            </>
          ) : null}
        </Card>

        {/* Map placeholder */}
        <HardShadow
          offset={Shadows.card}
          radius={Radii.lg}
          containerStyle={styles.mapWrapper}
        >
          <Pressable
            style={styles.mapPlaceholder}
            onPress={handleOpenMaps}
            accessibilityLabel="Open location in Maps"
          >
            <Ionicons name="map-outline" size={36} color={Colors.muted} />
            <Text style={styles.mapLabel}>TAP TO OPEN IN MAPS</Text>
            <Text style={styles.mapAddress} numberOfLines={2}>
              {workOrder.address}
            </Text>
            {workOrder.lat && workOrder.lng ? (
              <Text style={styles.mapCoords}>
                {workOrder.lat.toFixed(5)}, {workOrder.lng.toFixed(5)}
              </Text>
            ) : null}
          </Pressable>
        </HardShadow>

        {/* Action Buttons */}
        {!isDone ? (
          <View style={styles.actionSection}>
            <Text style={styles.sectionLabel}>ACTIONS</Text>

            {workOrder.status === 'OPEN' ? (
              <Button
                title="ACCEPT & START"
                onPress={handleQuickAccept}
                variant="wine"
                loading={mutation.isPending}
                style={styles.actionBtn}
              />
            ) : null}

            <View style={styles.actionRow}>
              <View style={styles.actionHalf}>
                <Button
                  title="ADD EVIDENCE"
                  onPress={() => router.push(`/work-order/evidence/${id}` as any)}
                  variant="secondary"
                  size="default"
                />
              </View>
              <View style={styles.actionHalf}>
                <Button
                  title="COMPLETE"
                  onPress={() => router.push(`/work-order/complete/${id}` as any)}
                  variant="primary"
                  size="default"
                />
              </View>
            </View>

            {workOrder.status === 'IN_PROGRESS' ? (
              <Button
                title="UPDATE STATUS"
                onPress={() => router.push(`/work-order/start/${id}` as any)}
                variant="ghost"
                size="default"
                style={styles.ghostBtn}
              />
            ) : null}
          </View>
        ) : (
          <Card shadow="hard" containerStyle={styles.cardMargin}>
            <View style={styles.closedBanner}>
              <Ionicons
                name={workOrder.status === 'DONE' ? 'checkmark-circle' : 'close-circle'}
                size={24}
                color={workOrder.status === 'DONE' ? Colors.wine : Colors.muted}
              />
              <Text style={styles.closedText}>
                {workOrder.status === 'DONE' ? 'Work order resolved' : 'Work order cancelled'}
              </Text>
            </View>
            {workOrder.closedAt ? (
              <Text style={styles.closedDate}>
                {new Date(workOrder.closedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
              </Text>
            ) : null}
          </Card>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.ground },
  scrollContent: { paddingBottom: 48 },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    paddingHorizontal: Spacing.screenH,
    marginBottom: 16,
  },
  section: { paddingHorizontal: Spacing.screenH, marginBottom: 16 },
  workTitle: {
    fontFamily: FontFamily.display,
    fontSize: 22,
    color: Colors.ink,
    lineHeight: 28,
  },
  cardMargin: { marginHorizontal: Spacing.screenH, marginBottom: 16, width: undefined },
  sectionLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 12,
  },
  description: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.body,
    color: Colors.ink,
    lineHeight: 24,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 12,
  },
  infoContent: { flex: 1 },
  infoLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  infoValue: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.body,
    color: Colors.ink,
  },
  infoLink: { color: Colors.wine, textDecorationLine: 'underline' },
  rowDivider: { height: 1, backgroundColor: Colors.dot },
  mapWrapper: {
    marginHorizontal: Spacing.screenH,
    marginBottom: 16,
  },
  mapPlaceholder: {
    height: 140,
    backgroundColor: Colors.dot,
    borderRadius: Radii.lg,
    borderWidth: 2,
    borderColor: Colors.ink,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    padding: 16,
  },
  mapLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1,
  },
  mapAddress: {
    fontFamily: FontFamily.sans,
    fontSize: 13,
    color: Colors.ink,
    textAlign: 'center',
  },
  mapCoords: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    color: Colors.muted,
  },
  actionSection: {
    paddingHorizontal: Spacing.screenH,
    gap: 10,
  },
  actionBtn: { width: '100%' },
  actionRow: { flexDirection: 'row', gap: 10 },
  actionHalf: { flex: 1 },
  ghostBtn: { marginTop: 4 },
  closedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 6,
  },
  closedText: {
    fontFamily: FontFamily.sansSemiBold,
    fontSize: FontSizes.body,
    color: Colors.ink,
  },
  closedDate: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.small,
    color: Colors.muted,
    marginLeft: 34,
  },
});
