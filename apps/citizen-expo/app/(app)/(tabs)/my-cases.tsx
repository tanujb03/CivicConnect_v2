import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';
import { MOCK_CASES } from '../../../src/data/mockData';
import type { CivicCase } from '../../../src/types';

type Tab = 'active' | 'awaiting_me' | 'resolved' | 'reopened' | 'supported';
const TABS: { key: Tab; label: string; count?: number }[] = [
  { key: 'active', label: 'Active', count: 4 },
  { key: 'awaiting_me', label: 'Awaiting me', count: 1 },
  { key: 'resolved', label: 'Resolved', count: 7 },
  { key: 'reopened', label: 'Reopened' },
];
const CATEGORIES = ['Category', 'Status', 'Date'];

function CaseListItem({ item }: { item: CivicCase }) {
  const router = useRouter();
  const getStatusConfig = (status: string) => {
    switch(status) {
      case 'verification_requested': return { label: 'Awaiting you', bg: Colors.ink, color: Colors.surface };
      case 'in_progress': return { label: 'In progress', bg: Colors.surface, color: Colors.ink, border: true };
      default: return { label: status, bg: Colors.surface, color: Colors.ink, border: true };
    }
  };
  const statusConfig = getStatusConfig(item.status);
  const getPriorityConfig = (priority: string) => {
    switch(priority) {
      case 'critical': return { label: 'URGENT', bg: Colors.fire, color: Colors.surface };
      case 'high': return { label: 'HIGH', bg: Colors.amber, color: Colors.ink };
      case 'medium': return { label: 'NORMAL', bg: Colors.surface, color: Colors.ink, border: true };
      case 'low': return { label: 'LOW', bg: Colors.surface, color: Colors.ink, border: true };
      default: return { label: priority.toUpperCase(), bg: Colors.surface, color: Colors.ink, border: true };
    }
  };
  const priorityConfig = getPriorityConfig(item.priority);
  const isVerification = item.status === 'verification_requested';
  const cardBg = isVerification ? Colors.lime : Colors.surface;

  return (
    <View style={styles.caseItemContainer}>
      <View style={styles.caseItemShadow} />
      <TouchableOpacity
        style={[styles.caseItem, { backgroundColor: cardBg }]}
        onPress={() => router.push(`/(app)/case/${item.id}`)}
        activeOpacity={0.9}
      >
        <View style={styles.caseItemTop}>
          <View style={[styles.statusPill, { backgroundColor: statusConfig.bg }, statusConfig.border && { borderWidth: 1.5, borderColor: Colors.ink }]}>
            <Text style={[styles.statusPillText, { color: statusConfig.color }]}>{statusConfig.label}</Text>
          </View>
          <View style={[styles.priorityPill, { backgroundColor: priorityConfig.bg }, priorityConfig.border && { borderWidth: 1.5, borderColor: Colors.ink }]}>
            <Text style={[styles.priorityPillText, { color: priorityConfig.color }]}>{priorityConfig.label}</Text>
          </View>
        </View>
        <Text style={styles.caseTitle}>{item.title}</Text>
        <Text style={styles.caseMeta}>
          {item.category.replace(/_/g, ' ')} · {isVerification ? 'updated today' : `${item.supporter_count} neighbours back this`}
        </Text>
        <View style={styles.caseFooter}>
          <Text style={styles.caseId}>{item.case_number}</Text>
          {isVerification && <Text style={styles.confirmText}>Confirm the fix →</Text>}
        </View>
      </TouchableOpacity>
    </View>
  );
}

export default function MyCasesScreen() {
  const params = useLocalSearchParams<{ tab?: Tab }>();
  const [activeTab, setActiveTab] = useState<Tab>(params.tab ?? 'active');
  const [cases, setCases] = useState<CivicCase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setTimeout(() => {
      setCases(MOCK_CASES);
      setLoading(false);
    }, 500);
  }, [activeTab]);

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.breadcrumb}>C07 • MY CASES</Text>
          <View style={styles.titleRow}>
            <Text style={styles.titleMy}>MY</Text>
            <View style={styles.titleCasesBadgeContainer}>
              <View style={styles.titleCasesBadgeShadow} />
              <View style={styles.titleCasesBadge}>
                <Text style={styles.titleCasesText}>CASES</Text>
              </View>
            </View>
            <View style={{flex: 1}}/>
            <TouchableOpacity style={styles.notifBtn} onPress={() => {}}>
              <View style={styles.notifShadow} />
              <View style={styles.notifBtnInner}>
                <Text style={styles.notifIcon}>🔔</Text>
                <View style={styles.notifBadge} />
              </View>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.tabsWrapper}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabList}>
            {TABS.map(t => {
              const isActive = activeTab === t.key;
              return (
                <View key={t.key} style={styles.tabItemContainer}>
                  <View style={styles.tabItemShadow} />
                  <TouchableOpacity style={[styles.tabItem, isActive && styles.tabItemActive]} onPress={() => setActiveTab(t.key)} activeOpacity={0.8}>
                    <Text style={styles.tabItemText}>
                      {t.label} {t.count !== undefined && <Text style={styles.tabItemCount}>{t.count}</Text>}
                    </Text>
                  </TouchableOpacity>
                </View>
              );
            })}
          </ScrollView>
        </View>

        <View style={styles.filtersWrapper}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterList}>
            {CATEGORIES.map(cat => (
              <View key={cat} style={styles.filterItemContainer}>
                <View style={styles.filterItemShadow} />
                <TouchableOpacity style={styles.filterItem} activeOpacity={0.8}>
                  <Text style={styles.filterItemText}>{cat} ▾</Text>
                </TouchableOpacity>
              </View>
            ))}
          </ScrollView>
        </View>

        {loading ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={Colors.ink} />
          </View>
        ) : (
          <FlatList
            data={cases}
            keyExtractor={c => c.id}
            renderItem={({ item }) => <CaseListItem item={item} />}
            contentContainerStyle={styles.list}
            showsVerticalScrollIndicator={false}
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.ground },
  container: { flex: 1 },
  header: { paddingHorizontal: Spacing[4], paddingTop: Spacing[4], marginBottom: Spacing[4] },
  breadcrumb: { fontFamily: 'monospace', fontSize: 12, color: Colors.muted, marginBottom: Spacing[2], letterSpacing: 1 },
  titleRow: { flexDirection: 'row', alignItems: 'center' },
  titleMy: { fontSize: 42, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1, marginRight: Spacing[2] },
  titleCasesBadgeContainer: { marginTop: 4 },
  titleCasesBadgeShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.sm },
  titleCasesBadge: { backgroundColor: Colors.ink, paddingHorizontal: Spacing[3], paddingVertical: 2, borderRadius: Radii.sm, borderWidth: 2, borderColor: Colors.surface },
  titleCasesText: { color: Colors.lime, fontSize: 28, fontWeight: Typography.black, letterSpacing: -0.5 },
  notifBtn: { width: 44, height: 44 },
  notifShadow: { position: 'absolute', top: 2, left: 2, width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.ink },
  notifBtnInner: { width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  notifIcon: { fontSize: 18 },
  notifBadge: { position: 'absolute', top: 8, right: 8, width: 10, height: 10, borderRadius: 5, backgroundColor: Colors.fire, borderWidth: 1.5, borderColor: Colors.ink },
  tabsWrapper: { marginBottom: Spacing[3] },
  tabList: { paddingHorizontal: Spacing[4], gap: Spacing[2] },
  tabItemContainer: { marginRight: Spacing[1] },
  tabItemShadow: { position: 'absolute', top: 2, left: 2, right: -2, bottom: -2, backgroundColor: Colors.ink, borderRadius: Radii.full },
  tabItem: { backgroundColor: Colors.surface, paddingHorizontal: Spacing[4], paddingVertical: Spacing[2], borderRadius: Radii.full, borderWidth: 1.5, borderColor: Colors.ink },
  tabItemActive: { backgroundColor: Colors.lime },
  tabItemText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  tabItemCount: { fontWeight: Typography.bold },
  filtersWrapper: { marginBottom: Spacing[4] },
  filterList: { paddingHorizontal: Spacing[4], gap: Spacing[2] },
  filterItemContainer: { marginRight: Spacing[1] },
  filterItemShadow: { position: 'absolute', top: 2, left: 2, right: -2, bottom: -2, backgroundColor: Colors.ink, borderRadius: Radii.md },
  filterItem: { backgroundColor: Colors.surface, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1.5], borderRadius: Radii.md, borderWidth: 1.5, borderColor: Colors.ink },
  filterItemText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  list: { paddingHorizontal: Spacing[4], paddingBottom: Layout.bottomNavHeight + Spacing[10] },
  caseItemContainer: { marginBottom: Spacing[4] },
  caseItemShadow: { position: 'absolute', top: 6, left: 6, right: -6, bottom: -6, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  caseItem: { borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4] },
  caseItemTop: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing[3] },
  statusPill: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  statusPillText: { fontSize: 12, fontWeight: Typography.bold },
  priorityPill: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  priorityPillText: { fontSize: 10, fontWeight: Typography.bold },
  caseTitle: { fontSize: 20, fontWeight: Typography.bold, color: Colors.ink, marginBottom: Spacing[2], lineHeight: 26 },
  caseMeta: { fontSize: 14, color: Colors.muted, marginBottom: Spacing[4] },
  caseFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  caseId: { fontFamily: 'monospace', fontSize: 12, color: Colors.muted },
  confirmText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  loadingBox: { paddingTop: Spacing[10], alignItems: 'center' },
});
