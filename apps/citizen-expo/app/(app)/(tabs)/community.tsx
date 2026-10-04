/**
 * C10 — Community
 *
 * Collective civic evidence layer:
 * - Tab switcher: Trending (sorted by supporters/upvotes) vs Latest (sorted by date)
 * - Category filter pills: All, Roads, Sanitation, Water, Lighting, Drainage
 * - Feed cards with photo thumbnails, category icons, status pills, distance & landmarks
 * - Interactive Support/Heart button with real-time local counter toggle
 * - Direct deep-link to Case Detail
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
  Image,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as Location from 'expo-location';
import { Colors, Typography, Spacing, Radii, Shadows, Layout, STATUS_LABELS, CATEGORY_ICONS } from '../../../src/constants/theme';
import { communityApi, casesApi } from '../../../src/api/client';
import { MOCK_COMMUNITY_ACTIVITY } from '../../../src/data/mockData';
import type { CommunityActivity, IssueCategory } from '../../../src/types';

interface ActivityItemWithExtras extends CommunityActivity {
  image?: string;
  landmark?: string;
  date?: string;
  created_at?: string;
}

const CATEGORIES: { key: string; label: string; icon: string }[] = [
  { key: 'all', label: 'All', icon: '🌐' },
  { key: 'roads', label: 'Roads', icon: '🛣️' },
  { key: 'sanitation', label: 'Sanitation', icon: '🗑️' },
  { key: 'water', label: 'Water', icon: '💧' },
  { key: 'lighting', label: 'Lighting', icon: '💡' },
  { key: 'drainage', label: 'Drainage', icon: '🌊' },
];

function ActivityCard({
  item,
  isSupported,
  onToggleSupport,
}: {
  item: ActivityItemWithExtras;
  isSupported: boolean;
  onToggleSupport: (caseId: string) => void;
}) {
  const router = useRouter();
  const statusColor = (Colors.status as any)[item.status] ?? Colors.neutral[400];

  const dist = item.distance_meters != null
    ? item.distance_meters < 1000
      ? `${Math.round(item.distance_meters)}m`
      : `${(item.distance_meters / 1000).toFixed(1)}km`
    : null;

  return (
    <View style={styles.card}>
      {item.image && (
        <TouchableOpacity
          activeOpacity={0.9}
          onPress={() => router.push(`/(app)/case/${item.case_id}`)}
        >
          <Image source={{ uri: item.image }} style={styles.cardImage} />
        </TouchableOpacity>
      )}

      <View style={styles.cardBody}>
        <View style={styles.cardTop}>
          <Text style={styles.cardCaseNum}>{item.case_number}</Text>
          <View style={[styles.statusPill, { backgroundColor: statusColor + '18' }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusPillText, { color: statusColor }]}>
              {STATUS_LABELS[item.status] ?? item.status}
            </Text>
          </View>
        </View>

        <TouchableOpacity
          onPress={() => router.push(`/(app)/case/${item.case_id}`)}
          accessibilityRole="button"
          accessibilityLabel={item.case_number + ': ' + item.title}
        >
          <Text style={styles.cardTitle} numberOfLines={2}>{item.title}</Text>
        </TouchableOpacity>

        <View style={styles.cardMeta}>
          <Text style={styles.cardCategory}>
            {CATEGORY_ICONS[item.category] ?? '⚠️'} {item.category.replace(/_/g, ' ')}
          </Text>
          {item.landmark && (
            <Text style={styles.cardLandmark} numberOfLines={1}>📍 {item.landmark}</Text>
          )}
          {dist && <Text style={styles.cardDist}>• {dist}</Text>}
        </View>

        <View style={styles.cardFooter}>
          <Text style={styles.cardSupporters}>
            👥 {item.supporter_count} supporters
          </Text>

          <TouchableOpacity
            style={[styles.heartBtn, isSupported && styles.heartBtnActive]}
            onPress={() => onToggleSupport(item.case_id)}
            accessibilityRole="button"
            accessibilityLabel="Upvote / Support this case"
          >
            <Text style={styles.heartIcon}>{isSupported ? '❤️' : '🤍'}</Text>
            <Text style={[styles.heartText, isSupported && styles.heartTextActive]}>
              {isSupported ? 'Supported' : 'Support'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

export default function CommunityScreen() {
  const [activity, setActivity] = useState<ActivityItemWithExtras[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'trending' | 'latest'>('trending');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [supportedCases, setSupportedCases] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      let data: ActivityItemWithExtras[] = [];
      const { status } = await Location.requestForegroundPermissionsAsync().catch(() => ({ status: 'denied' }));
      if (status === 'granted') {
        const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
        if (pos) {
          data = await communityApi.nearby(pos.coords.latitude, pos.coords.longitude, 5).catch(() => []);
        }
      }
      if (!data || data.length === 0) {
        data = MOCK_COMMUNITY_ACTIVITY;
      }
      setActivity(data);
    } catch {
      setActivity(MOCK_COMMUNITY_ACTIVITY);
    }
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const handleToggleSupport = (caseId: string) => {
    const isCurrentlySupported = !!supportedCases[caseId];
    setSupportedCases(prev => ({ ...prev, [caseId]: !isCurrentlySupported }));

    setActivity(prev =>
      prev.map(item => {
        if (item.case_id === caseId) {
          return {
            ...item,
            supporter_count: item.supporter_count + (isCurrentlySupported ? -1 : 1),
          };
        }
        return item;
      })
    );

    casesApi.support(caseId).catch(() => { });
  };

  // Filter & Sort
  const filtered = activity.filter(
    item => categoryFilter === 'all' || item.category === categoryFilter
  );

  const sorted = [...filtered].sort((a, b) => {
    if (activeTab === 'trending') {
      return (b.supporter_count ?? 0) - (a.supporter_count ?? 0);
    }
    const dateA = a.created_at ? new Date(a.created_at).getTime() : (a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0);
    const dateB = b.created_at ? new Date(b.created_at).getTime() : (b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0);
    return dateB - dateA;
  });

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View style={styles.headerTitleRow}>
            <View style={styles.headerIconBox}>
              <Text style={styles.headerIcon}>👥</Text>
            </View>
            <View>
              <Text style={styles.headerTitle}>Community Activity</Text>
              <Text style={styles.headerSub}>Collective civic evidence layer</Text>
            </View>
          </View>
          <View style={styles.headerCountBadge}>
            <Text style={styles.headerCountText}>{sorted.length} cases</Text>
          </View>
        </View>

        {/* Trending vs Latest Switcher Tabs */}
        <View style={styles.tabBar}>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'trending' && styles.tabBtnActive]}
            onPress={() => setActiveTab('trending')}
          >
            <Text style={[styles.tabBtnText, activeTab === 'trending' && styles.tabBtnTextActive]}>
              🔥 Trending
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'latest' && styles.tabBtnActive]}
            onPress={() => setActiveTab('latest')}
          >
            <Text style={[styles.tabBtnText, activeTab === 'latest' && styles.tabBtnTextActive]}>
              ⏱️ Latest
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ─── Category Filter Pills ──────────────────────────── */}
      <View style={styles.filterSection}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {CATEGORIES.map(cat => {
            const isSelected = categoryFilter === cat.key;
            return (
              <TouchableOpacity
                key={cat.key}
                style={[styles.filterPill, isSelected && styles.filterPillActive]}
                onPress={() => setCategoryFilter(cat.key)}
              >
                <Text style={styles.filterPillIcon}>{cat.icon}</Text>
                <Text style={[styles.filterPillText, isSelected && styles.filterPillTextActive]}>
                  {cat.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Info Strip */}
      <View style={styles.infoStrip}>
        <Text style={styles.infoText}>
          💡 Support cases to prioritize them in municipal routing. Verified community evidence speeds up dispatch.
        </Text>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#0D4A1A" />
        </View>
      ) : sorted.length === 0 ? (
        <View style={styles.center}>
          <Text style={{ fontSize: 44, marginBottom: Spacing[2] }}>🏙️</Text>
          <Text style={styles.emptyTitle}>No cases found</Text>
          <Text style={styles.emptySub}>No civic cases matched the selected category filter.</Text>
        </View>
      ) : (
        <FlatList
          data={sorted}
          keyExtractor={a => a.case_id}
          renderItem={({ item }) => (
            <ActivityCard
              item={item}
              isSupported={!!supportedCases[item.case_id]}
              onToggleSupport={handleToggleSupport}
            />
          )}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0D4A1A" />
          }
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAF9' },
  header: {
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[4],
    backgroundColor: '#0D4A1A',
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[3.5],
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3],
  },
  headerIconBox: {
    width: 40,
    height: 40,
    borderRadius: Radii.lg,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerIcon: { fontSize: 20 },
  headerTitle: {
    fontSize: Typography.lg,
    fontWeight: Typography.extrabold,
    color: '#fff',
    letterSpacing: -0.3,
  },
  headerSub: {
    fontSize: Typography.xs,
    color: 'rgba(255,255,255,0.65)',
    marginTop: 1,
  },
  headerCountBadge: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    paddingHorizontal: Spacing[3],
    paddingVertical: 4,
    borderRadius: Radii.full,
  },
  headerCountText: {
    color: '#fff',
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: Radii.xl,
    padding: 3,
  },
  tabBtn: {
    flex: 1,
    paddingVertical: Spacing[2],
    alignItems: 'center',
    borderRadius: Radii.lg,
  },
  tabBtnActive: {
    backgroundColor: '#fff',
    ...Shadows.sm,
  },
  tabBtnText: {
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
    color: 'rgba(255,255,255,0.7)',
  },
  tabBtnTextActive: {
    color: '#0D4A1A',
  },

  filterSection: {
    paddingVertical: Spacing[3],
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
  },
  filterRow: {
    paddingHorizontal: Spacing[5],
    gap: Spacing[2],
  },
  filterPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing[3.5],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[100],
  },
  filterPillActive: {
    backgroundColor: '#10B981',
  },
  filterPillIcon: { fontSize: 13 },
  filterPillText: {
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    color: Colors.neutral[600],
  },
  filterPillTextActive: { color: '#fff' },

  infoStrip: {
    backgroundColor: '#ECFDF5',
    paddingHorizontal: Spacing[5],
    paddingVertical: Spacing[2.5],
    borderBottomWidth: 1,
    borderBottomColor: '#D1FAE5',
  },
  infoText: {
    fontSize: 11,
    color: '#065F46',
    lineHeight: 16,
  },

  list: {
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[3],
    paddingBottom: Layout.bottomNavHeight + Spacing[6],
  },

  card: {
    backgroundColor: '#fff',
    borderRadius: Radii.xl,
    marginBottom: Spacing[3.5],
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.neutral[100],
    ...Shadows.sm,
  },
  cardImage: {
    width: '100%',
    height: 160,
    backgroundColor: '#E2E8F0',
  },
  cardBody: {
    padding: Spacing[4],
  },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  cardCaseNum: {
    fontSize: 11,
    fontWeight: Typography.bold,
    color: Colors.neutral[400],
    letterSpacing: 0.5,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing[2.5],
    paddingVertical: 2,
    borderRadius: Radii.full,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusPillText: { fontSize: 10, fontWeight: Typography.bold },
  cardTitle: {
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    lineHeight: 22,
    marginBottom: 6,
  },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[2],
    marginBottom: Spacing[3],
  },
  cardCategory: {
    fontSize: Typography.xs,
    color: Colors.neutral[500],
    textTransform: 'capitalize',
  },
  cardLandmark: {
    fontSize: Typography.xs,
    color: Colors.neutral[400],
    maxWidth: 140,
  },
  cardDist: {
    fontSize: Typography.xs,
    color: Colors.neutral[400],
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[100],
    paddingTop: Spacing[3],
  },
  cardSupporters: {
    fontSize: Typography.xs,
    color: Colors.neutral[500],
    fontWeight: Typography.semibold,
  },
  heartBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.neutral[50],
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
  },
  heartBtnActive: {
    backgroundColor: '#FEE2E2',
    borderColor: '#FCA5A5',
  },
  heartIcon: { fontSize: 14 },
  heartText: {
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
    color: Colors.neutral[600],
  },
  heartTextActive: {
    color: '#DC2626',
  },

  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing[8],
  },
  emptyTitle: {
    fontSize: Typography.lg,
    fontWeight: Typography.bold,
    color: Colors.neutral[800],
  },
  emptySub: {
    fontSize: Typography.sm,
    color: Colors.neutral[400],
    textAlign: 'center',
    marginTop: 4,
  },
});
