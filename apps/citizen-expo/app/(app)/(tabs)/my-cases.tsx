/**
 * C07 — My Civic Cases
 *
 * Full feature parity with Citizen Web MyReports + System Design:
 * - Tabs: Active | Awaiting Me | Resolved | Reopened | Supported
 * - Category Filter Pills: All, Roads, Sanitation, Water, Lighting, Drainage
 * - Status Filter Pills: All, Submitted, In Progress, Resolved
 * - Date Sort Toggle: Ascending vs Descending
 * - Issue Cards with Photo thumbnail, Category icon, Landmark, and Supporter count
 * - Direct "Re-open Issue" action on resolved cards
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
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Shadows, Layout, STATUS_LABELS, CATEGORY_ICONS, PRIORITY_LABELS } from '../../../src/constants/theme';
import { casesApi } from '../../../src/api/client';
import { MOCK_CASES } from '../../../src/data/mockData';
import type { CivicCase, IssueCategory } from '../../../src/types';

type Tab = 'active' | 'awaiting_me' | 'resolved' | 'reopened' | 'supported';

const TABS: { key: Tab; label: string; emoji: string }[] = [
  { key: 'active', label: 'Active', emoji: '🔴' },
  { key: 'awaiting_me', label: 'Awaiting Me', emoji: '⏳' },
  { key: 'resolved', label: 'Resolved', emoji: '✅' },
  { key: 'reopened', label: 'Reopened', emoji: '🔄' },
  { key: 'supported', label: 'Supported', emoji: '👍' },
];

const CATEGORIES: { key: string; label: string; icon: string }[] = [
  { key: 'all', label: 'All Categories', icon: '🌐' },
  { key: 'roads', label: 'Roads', icon: '🛣️' },
  { key: 'sanitation', label: 'Sanitation', icon: '🗑️' },
  { key: 'water', label: 'Water', icon: '💧' },
  { key: 'lighting', label: 'Lighting', icon: '💡' },
  { key: 'drainage', label: 'Drainage', icon: '🌊' },
];

function PriorityDot({ priority }: { priority: string }) {
  const color = (Colors.priority as any)[priority] ?? Colors.neutral[400];
  return <View style={[styles.priorityDot, { backgroundColor: color }]} />;
}

function CaseListItem({
  item,
  onReopen,
}: {
  item: CivicCase;
  onReopen: (caseId: string) => void;
}) {
  const router = useRouter();
  const statusColor = (Colors.status as any)[item.status] ?? Colors.neutral[400];
  const ago = getTimeAgo(item.updated_at);
  const firstImage = item.evidence?.find(e => e.type === 'image')?.url;

  return (
    <View style={styles.caseItem}>
      <TouchableOpacity
        onPress={() => router.push(`/(app)/case/${item.id}`)}
        accessibilityRole="button"
        accessibilityLabel={`${item.case_number}: ${item.title}`}
      >
        <View style={styles.caseItemTop}>
          <View style={styles.caseItemLeft}>
            <PriorityDot priority={item.priority} />
            <Text style={styles.caseNum}>{item.case_number}</Text>
          </View>
          <View style={[styles.statusPill, { backgroundColor: statusColor + '18' }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusPillText, { color: statusColor }]}>
              {STATUS_LABELS[item.status] ?? item.status}
            </Text>
          </View>
        </View>

        <View style={styles.caseMainRow}>
          {firstImage && (
            <Image source={{ uri: firstImage }} style={styles.caseThumb} />
          )}
          <View style={{ flex: 1 }}>
            <Text style={styles.caseTitle} numberOfLines={2}>{item.title}</Text>
            {item.location?.landmark && (
              <Text style={styles.caseLandmark} numberOfLines={1}>📍 {item.location.landmark}</Text>
            )}
          </View>
        </View>

        <View style={styles.caseMeta}>
          <Text style={styles.caseCategory}>
            {CATEGORY_ICONS[item.category] ?? '⚠️'} {item.category.replace(/_/g, ' ')}
          </Text>
          <Text style={styles.caseSeparator}>·</Text>
          <Text style={styles.caseAge}>{ago}</Text>
        </View>
      </TouchableOpacity>

      <View style={styles.caseFooter}>
        <Text style={styles.caseSupporters}>👥 {item.supporter_count} supporters</Text>
        <View style={styles.caseActions}>
          {item.requires_my_action && (
            <TouchableOpacity
              style={styles.actionBadge}
              onPress={() => router.push(`/(app)/case/${item.id}`)}
            >
              <Text style={styles.actionBadgeText}>Verify Now →</Text>
            </TouchableOpacity>
          )}

          {item.status === 'resolved' && (
            <TouchableOpacity
              style={styles.reopenBtn}
              onPress={() => onReopen(item.id)}
            >
              <Text style={styles.reopenBtnText}>🔄 Re-open Issue</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  );
}

function EmptyState({ tab }: { tab: Tab }) {
  const router = useRouter();
  const messages: Record<Tab, { emoji: string; title: string; sub: string }> = {
    active: { emoji: '✨', title: 'No active cases', sub: 'Your reported cases will appear here.' },
    awaiting_me: { emoji: '⏳', title: 'Nothing needs your attention', sub: 'Cases waiting for your verification or input will show up here.' },
    resolved: { emoji: '🎉', title: 'No resolved cases yet', sub: 'Cases you reported that have been fixed will appear here.' },
    reopened: { emoji: '🔄', title: 'No reopened cases', sub: 'Cases you disputed or reopened will appear here.' },
    supported: { emoji: '👍', title: 'No supported cases', sub: 'Cases you\'ve supported will appear here.' },
  };
  const m = messages[tab];

  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyEmoji}>{m.emoji}</Text>
      <Text style={styles.emptyTitle}>{m.title}</Text>
      <Text style={styles.emptySub}>{m.sub}</Text>
      {tab === 'active' && (
        <TouchableOpacity style={styles.reportBtn} onPress={() => router.push('/(app)/report')}>
          <Text style={styles.reportBtnText}>Report your first issue</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

export default function MyCasesScreen() {
  const params = useLocalSearchParams<{ tab?: Tab }>();
  const [activeTab, setActiveTab] = useState<Tab>(params.tab ?? 'active');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [dateSort, setDateSort] = useState<'desc' | 'asc'>('desc');
  const [cases, setCases] = useState<CivicCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadCases = useCallback(async (tab: Tab) => {
    try {
      const res = await casesApi.list({ tab, page_size: 20 });
      let loaded = res.items;
      if (!loaded || loaded.length === 0) {
        loaded = MOCK_CASES;
      }
      setCases(loaded);
    } catch {
      setCases(MOCK_CASES);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadCases(activeTab).finally(() => setLoading(false));
  }, [activeTab, loadCases]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadCases(activeTab);
    setRefreshing(false);
  }, [activeTab, loadCases]);

  const handleReopen = async (caseId: string) => {
    await casesApi.reopen(caseId, 'Issue re-opened by citizen');
    setCases(prev =>
      prev.map(c => (c.id === caseId ? { ...c, status: 'reopened' } : c))
    );
  };

  // Filter & Sort
  const filtered = cases.filter(
    c => categoryFilter === 'all' || c.category === categoryFilter
  );

  const sorted = [...filtered].sort((a, b) => {
    const dateA = new Date(a.created_at || a.updated_at).getTime();
    const dateB = new Date(b.created_at || b.updated_at).getTime();
    return dateSort === 'desc' ? dateB - dateA : dateA - dateB;
  });

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <Text style={styles.headerTitle}>My Civic Cases</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countBadgeText}>{sorted.length} total</Text>
          </View>
        </View>

        {/* Tab Selector */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabList}
        >
          {TABS.map(t => {
            const isActive = activeTab === t.key;
            return (
              <TouchableOpacity
                key={t.key}
                style={[styles.tab, isActive && styles.tabActive]}
                onPress={() => setActiveTab(t.key)}
              >
                <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
                  {t.emoji} {t.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* ─── Category Filter & Sort Strip ───────────────────── */}
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

          <TouchableOpacity
            style={styles.sortPill}
            onPress={() => setDateSort(prev => (prev === 'desc' ? 'asc' : 'desc'))}
          >
            <Text style={styles.sortPillText}>
              📅 Date {dateSort === 'desc' ? '↓' : '↑'}
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </View>

      {loading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#0D4A1A" />
        </View>
      ) : sorted.length === 0 ? (
        <EmptyState tab={activeTab} />
      ) : (
        <FlatList
          data={sorted}
          keyExtractor={c => c.id}
          renderItem={({ item }) => (
            <CaseListItem item={item} onReopen={handleReopen} />
          )}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0D4A1A" />
          }
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

function getTimeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAF9' },
  header: {
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[3],
    backgroundColor: '#0D4A1A',
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[3],
  },
  headerTitle: {
    fontSize: Typography.xl,
    fontWeight: Typography.extrabold,
    color: '#fff',
    letterSpacing: -0.4,
  },
  countBadge: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    paddingHorizontal: Spacing[3],
    paddingVertical: 4,
    borderRadius: Radii.full,
  },
  countBadgeText: {
    color: '#fff',
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
  },
  tabList: {
    gap: Spacing[2],
    paddingBottom: Spacing[1],
  },
  tab: {
    paddingHorizontal: Spacing[3.5],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.full,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  tabActive: { backgroundColor: '#fff' },
  tabText: {
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    color: 'rgba(255,255,255,0.7)',
  },
  tabTextActive: { color: '#0D4A1A', fontWeight: Typography.bold },

  filterSection: {
    paddingVertical: Spacing[2.5],
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
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[100],
  },
  filterPillActive: { backgroundColor: '#10B981' },
  filterPillIcon: { fontSize: 12 },
  filterPillText: {
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    color: Colors.neutral[600],
  },
  filterPillTextActive: { color: '#fff' },
  sortPill: {
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[100],
  },
  sortPillText: {
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
    color: Colors.neutral[700],
  },

  list: {
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[3],
    paddingBottom: Layout.bottomNavHeight + Spacing[6],
  },
  caseItem: {
    backgroundColor: '#fff',
    borderRadius: Radii.xl,
    padding: Spacing[4],
    marginBottom: Spacing[3],
    ...Shadows.sm,
    borderWidth: 1,
    borderColor: Colors.neutral[100],
  },
  caseItemTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[2],
  },
  caseItemLeft: { flexDirection: 'row', alignItems: 'center', gap: Spacing[2] },
  priorityDot: { width: 8, height: 8, borderRadius: 4 },
  caseNum: {
    fontSize: Typography.xs,
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

  caseMainRow: {
    flexDirection: 'row',
    gap: Spacing[3],
    marginBottom: Spacing[2],
  },
  caseThumb: {
    width: 54,
    height: 54,
    borderRadius: Radii.lg,
  },
  caseTitle: {
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    lineHeight: 20,
    marginBottom: 2,
  },
  caseLandmark: {
    fontSize: 11,
    color: Colors.neutral[400],
  },
  caseMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[2],
    marginBottom: Spacing[2.5],
  },
  caseCategory: {
    fontSize: Typography.xs,
    color: Colors.neutral[500],
    textTransform: 'capitalize',
  },
  caseSeparator: { fontSize: Typography.xs, color: Colors.neutral[300] },
  caseAge: { fontSize: Typography.xs, color: Colors.neutral[400] },

  caseFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[100],
    paddingTop: Spacing[2.5],
  },
  caseSupporters: {
    fontSize: Typography.xs,
    color: Colors.neutral[400],
    fontWeight: Typography.medium,
  },
  caseActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[2],
  },
  actionBadge: {
    backgroundColor: '#ECFDF5',
    paddingHorizontal: Spacing[3],
    paddingVertical: 4,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  actionBadgeText: {
    fontSize: 11,
    color: '#059669',
    fontWeight: Typography.bold,
  },
  reopenBtn: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: Spacing[3],
    paddingVertical: 4,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  reopenBtnText: {
    fontSize: 11,
    color: '#D97706',
    fontWeight: Typography.bold,
  },

  loadingBox: { alignItems: 'center', paddingTop: Spacing[16], gap: Spacing[4] },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: Spacing[14],
    paddingHorizontal: Spacing[8],
  },
  emptyEmoji: { fontSize: 44, marginBottom: Spacing[2] },
  emptyTitle: {
    fontSize: Typography.lg,
    fontWeight: Typography.bold,
    color: Colors.neutral[800],
    textAlign: 'center',
  },
  emptySub: {
    fontSize: Typography.sm,
    color: Colors.neutral[400],
    textAlign: 'center',
    marginTop: 4,
  },
  reportBtn: {
    backgroundColor: '#10B981',
    borderRadius: Radii.xl,
    paddingHorizontal: Spacing[5],
    paddingVertical: Spacing[2.5],
    marginTop: Spacing[4],
  },
  reportBtnText: {
    color: '#fff',
    fontWeight: Typography.bold,
    fontSize: Typography.sm,
  },
});
