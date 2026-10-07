import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Radii, Spacing } from '../../src/theme/tokens';
import { FontFamily } from '../../src/theme/fonts';
import { Card, StatusChip, PriorityChip, StateView } from '../../src/ui';
import { apiClient } from '../../src/api/client';
import type { WorkOrder } from '../../src/api/types';

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function DoneCard({ item, onPress }: { item: WorkOrder; onPress: () => void }) {
  return (
    <Card shadow="hard" containerStyle={styles.cardContainer} onPress={onPress}>
      <View style={styles.cardTop}>
        <PriorityChip priority={item.priority} size="sm" />
        <StatusChip status={item.status} size="sm" />
      </View>
      <Text style={styles.cardTitle} numberOfLines={2}>
        {item.title}
      </Text>
      <View style={styles.row}>
        <Ionicons name="location-outline" size={14} color={Colors.muted} />
        <Text style={styles.metaText} numberOfLines={1}>{item.address}</Text>
      </View>
      <View style={styles.cardFooter}>
        <Text style={styles.caseId}>#{item.caseId}</Text>
        {item.closedAt ? (
          <Text style={styles.dateText}>Closed {formatDate(item.closedAt)}</Text>
        ) : null}
      </View>
    </Card>
  );
}

export default function HistoryScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['workOrders', 'done'],
    queryFn: () => apiClient.getWorkOrders({ status: 'DONE' }),
  });

  const doneOrders = (data?.data ?? []).filter(
    (wo) => wo.status === 'DONE' || wo.status === 'CANCELLED'
  );

  const handlePress = useCallback((id: string) => {
    router.push(`/work-order/${id}` as any);
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: WorkOrder }) => (
      <DoneCard item={item} onPress={() => handlePress(item.id)} />
    ),
    [handlePress]
  );

  const ListHeader = (
    <View style={styles.header}>
      <Text style={styles.eyebrow}>COMPLETED WORK</Text>
      <Text style={styles.heading}>DONE</Text>
      <Text style={styles.subCount}>
        {doneOrders.length} resolved this session
      </Text>
    </View>
  );

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="loading" title="Loading history..." />
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView
          variant="error"
          title="Failed to load"
          actionLabel="Retry"
          onAction={() => refetch()}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <FlatList
        data={doneOrders}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={ListHeader}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={() => refetch()}
            tintColor={Colors.wine}
            colors={[Colors.wine]}
          />
        }
        ListEmptyComponent={
          <StateView
            variant="empty"
            title="Nothing resolved yet"
            message="Completed work orders will appear here"
          />
        }
        ItemSeparatorComponent={() => <View style={{ height: Spacing.cardGap }} />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.ground },
  listContent: { paddingHorizontal: Spacing.screenH, paddingBottom: 32 },
  header: { paddingTop: 20, paddingBottom: 20 },
  eyebrow: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.wine,
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  heading: {
    fontFamily: FontFamily.display,
    fontSize: 32,
    color: Colors.ink,
    letterSpacing: -1,
  },
  subCount: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.small,
    color: Colors.muted,
    marginTop: 4,
  },
  cardContainer: { width: '100%' },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  cardTitle: {
    fontFamily: FontFamily.sansSemiBold,
    fontSize: FontSizes.cardTitle,
    color: Colors.ink,
    marginBottom: 8,
    lineHeight: 24,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 10 },
  metaText: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.small,
    color: Colors.muted,
    flex: 1,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: Colors.dot,
    paddingTop: 10,
  },
  caseId: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    color: Colors.wine,
    fontWeight: '500',
  },
  dateText: {
    fontFamily: FontFamily.sans,
    fontSize: 12,
    color: Colors.muted,
  },
});
