import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  RefreshControl,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Radii, Shadows, Spacing } from '../../src/theme/tokens';
import { FontFamily } from '../../src/theme/fonts';
import {
  Card,
  PriorityChip,
  StatusChip,
  SlaChip,
  KpiCard,
  StateView,
  HardShadow,
  OfflineBanner,
} from '../../src/ui';
import { apiClient } from '../../src/api/client';
import type { WorkOrder } from '../../src/api/types';
import { useNetwork } from '../../src/theme/useNetwork';

const CATEGORIES: Record<string, string> = {
  ROAD: 'Road',
  WATER: 'Water',
  SEWER: 'Sewer',
  ELECTRICAL: 'Electrical',
  PARKS: 'Parks',
  DEBRIS: 'Debris',
  OTHER: 'Other',
};

function WorkOrderCard({ item, onPress }: { item: WorkOrder; onPress: () => void }) {
  return (
    <Card
      shadow="card"
      containerStyle={styles.cardContainer}
      onPress={onPress}
      accessibilityLabel={`Work order: ${item.title}`}
    >
      <View style={styles.cardTop}>
        <View style={styles.chipRow}>
          <PriorityChip priority={item.priority} size="sm" />
          <View style={styles.chipGap} />
          <StatusChip status={item.status} size="sm" />
        </View>
        <SlaChip deadline={item.slaDeadline} size="sm" />
      </View>

      <Text style={styles.cardTitle} numberOfLines={2}>
        {item.title}
      </Text>

      <View style={styles.cardMeta}>
        <Ionicons name="location-outline" size={14} color={Colors.muted} />
        <Text style={styles.metaText} numberOfLines={1}>
          {item.address}
        </Text>
      </View>

      <View style={styles.cardFooter}>
        <View style={styles.categoryTag}>
          <Text style={styles.categoryText}>{CATEGORIES[item.category] ?? item.category}</Text>
        </View>
        <Text style={styles.caseId}>#{item.caseId}</Text>
        <Ionicons name="chevron-forward" size={16} color={Colors.muted} />
      </View>
    </Card>
  );
}

function KpiStrip({ openCount, overdueCount, doneToday }: {
  openCount: number;
  overdueCount: number;
  doneToday: number;
}) {
  return (
    <View style={styles.kpiRow}>
      <KpiCard
        value={openCount}
        label="Open"
        backgroundColor={Colors.wine}
        textColor={Colors.lime}
        style={styles.kpiCardStyle}
      />
      <View style={styles.kpiGap} />
      <KpiCard
        value={overdueCount}
        label="Overdue"
        backgroundColor={overdueCount > 0 ? Colors.fire : Colors.surface}
        textColor={overdueCount > 0 ? Colors.onFire : Colors.ink}
        style={styles.kpiCardStyle}
      />
      <View style={styles.kpiGap} />
      <KpiCard
        value={doneToday}
        label="Done"
        backgroundColor={Colors.limeTint}
        textColor={Colors.ink}
        style={styles.kpiCardStyle}
      />
    </View>
  );
}

export default function AssignedScreen() {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'OPEN' | 'IN_PROGRESS'>('ALL');
  const { isOnline } = useNetwork();

  const {
    data,
    isLoading,
    isError,
    refetch,
    isRefetching,
  } = useQuery({
    queryKey: ['workOrders', 'assigned'],
    queryFn: () => apiClient.getWorkOrders({ status: 'active' }),
  });

  const { data: kpiData } = useQuery({
    queryKey: ['kpi'],
    queryFn: () => apiClient.getKpi(),
  });

  const workOrders = data?.data ?? [];

  const filtered = workOrders.filter((wo) => {
    const matchStatus =
      filterStatus === 'ALL' ? wo.status !== 'DONE' && wo.status !== 'CANCELLED' : wo.status === filterStatus;
    const matchSearch =
      !search ||
      wo.title.toLowerCase().includes(search.toLowerCase()) ||
      wo.address.toLowerCase().includes(search.toLowerCase()) ||
      wo.caseId.toLowerCase().includes(search.toLowerCase());
    return matchStatus && matchSearch;
  });

  const handlePress = useCallback((id: string) => {
    router.push(`/work-order/${id}` as any);
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: WorkOrder }) => (
      <WorkOrderCard item={item} onPress={() => handlePress(item.id)} />
    ),
    [handlePress]
  );

  const keyExtractor = useCallback((item: WorkOrder) => item.id, []);

  const ListHeader = (
    <>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>WARD 7 — NAGPUR</Text>
          <Text style={styles.heading}>ASSIGNED</Text>
        </View>
        <HardShadow offset={{ dx: 2, dy: 2 }} radius={Radii.md}>
          <Pressable
            style={styles.settingsBtn}
            onPress={() => router.push('/(tabs)/profile' as any)}
            accessibilityLabel="Profile"
          >
            <Ionicons name="person-outline" size={20} color={Colors.ink} />
          </Pressable>
        </HardShadow>
      </View>

      {/* Offline banner */}
      {!isOnline ? (
        <View style={styles.offlineBannerWrapper}>
          <OfflineBanner />
        </View>
      ) : null}

      {/* KPI strip */}
      {kpiData ? (
        <KpiStrip
          openCount={kpiData.openCount}
          overdueCount={kpiData.overdueCount}
          doneToday={kpiData.doneToday}
        />
      ) : null}

      {/* Search */}
      <HardShadow offset={Shadows.hard} radius={Radii.md} containerStyle={styles.searchWrapper}>
        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={Colors.muted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search work orders..."
            placeholderTextColor={Colors.muted}
            value={search}
            onChangeText={setSearch}
            returnKeyType="search"
            accessibilityLabel="Search work orders"
          />
          {search ? (
            <Pressable onPress={() => setSearch('')} hitSlop={8}>
              <Ionicons name="close-circle" size={18} color={Colors.muted} />
            </Pressable>
          ) : null}
        </View>
      </HardShadow>

      {/* Filter pills */}
      <View style={styles.filterRow}>
        {(['ALL', 'OPEN', 'IN_PROGRESS'] as const).map((f) => (
          <Pressable
            key={f}
            onPress={() => setFilterStatus(f)}
            style={[
              styles.filterPill,
              filterStatus === f && styles.filterPillActive,
            ]}
          >
            <Text
              style={[
                styles.filterText,
                filterStatus === f && styles.filterTextActive,
              ]}
            >
              {f === 'ALL' ? 'All' : f === 'IN_PROGRESS' ? 'In Progress' : 'Open'}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.countLabel}>
        {filtered.length} WORK ORDER{filtered.length !== 1 ? 'S' : ''}
      </Text>
    </>
  );

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="loading" title="Loading work orders..." />
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView
          variant="error"
          title="Failed to load"
          message="Could not fetch work orders"
          actionLabel="Retry"
          onAction={() => refetch()}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <FlatList
        data={filtered}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
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
            title="All clear!"
            message="No work orders match your filter"
          />
        }
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: Colors.ground,
  },
  listContent: {
    paddingHorizontal: Spacing.screenH,
    paddingBottom: 32,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingTop: 20,
    paddingBottom: 16,
  },
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
  settingsBtn: {
    width: 44,
    height: 44,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    backgroundColor: Colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 6,
  },
  offlineBannerWrapper: {
    marginBottom: 16,
  },
  kpiRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  kpiGap: {
    width: 8,
  },
  kpiCardStyle: {
    minHeight: 80,
    justifyContent: 'center',
  },
  searchWrapper: {
    marginBottom: 12,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    paddingHorizontal: 12,
    height: 46,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    color: Colors.ink,
    height: '100%',
  },
  filterRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  filterPill: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: Radii.full,
    borderWidth: 1.5,
    borderColor: Colors.ink,
    backgroundColor: Colors.surface,
  },
  filterPillActive: {
    backgroundColor: Colors.wine,
    borderColor: Colors.wine,
  },
  filterText: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    fontWeight: '500',
    color: Colors.ink,
  },
  filterTextActive: {
    color: Colors.onWine,
  },
  countLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1,
    marginBottom: 10,
  },
  cardContainer: {
    width: '100%',
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  chipRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  chipGap: {
    width: 6,
  },
  cardTitle: {
    fontFamily: FontFamily.sansSemiBold,
    fontSize: FontSizes.cardTitle,
    color: Colors.ink,
    marginBottom: 8,
    lineHeight: 24,
  },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 12,
  },
  metaText: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.small,
    color: Colors.muted,
    flex: 1,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: Colors.dot,
    paddingTop: 10,
    gap: 8,
  },
  categoryTag: {
    flex: 1,
  },
  categoryText: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  caseId: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    color: Colors.wine,
    fontWeight: '500',
  },
  separator: {
    height: Spacing.cardGap,
  },
});
