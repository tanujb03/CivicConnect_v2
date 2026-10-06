import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';
import { MOCK_COMMUNITY_ACTIVITY } from '../../../src/data/mockData';
import type { CommunityActivity } from '../../../src/types';

interface ActivityItemWithExtras extends CommunityActivity {
  image?: string;
  landmark?: string;
  date?: string;
  created_at?: string;
}

const CATEGORIES = ['Near me', 'Most backed', 'Needs a photo'];

function ActivityCard({ item, isSupported, onToggleSupport }: { item: ActivityItemWithExtras; isSupported: boolean; onToggleSupport: (caseId: string) => void; }) {
  const router = useRouter();
  const getStatusConfig = (status: string) => {
    switch(status) {
      case 'in_progress': return { label: 'In progress', bg: Colors.surface, color: Colors.ink, border: true };
      case 'assigned': return { label: 'Assigned', bg: Colors.surface, color: Colors.ink, border: true };
      default: return { label: 'Your report', bg: Colors.ink, color: Colors.surface, border: false };
    }
  };
  
  const statusConfig = getStatusConfig(item.status);
  const cardBg = item.status === 'verification_requested' ? Colors.limeTint : Colors.surface;

  return (
    <View style={styles.cardContainer}>
      <View style={styles.cardShadow} />
      <TouchableOpacity style={[styles.card, { backgroundColor: cardBg }]} activeOpacity={0.9} onPress={() => router.push(`/(app)/case/${item.case_id}`)}>
        <View style={styles.cardTop}>
          <View style={[styles.statusPill, { backgroundColor: statusConfig.bg }, statusConfig.border && { borderWidth: 1.5, borderColor: Colors.ink }]}>
            <Text style={[styles.statusPillText, { color: statusConfig.color }]}>{statusConfig.label}</Text>
          </View>
          <Text style={styles.caseId}>{item.case_number}</Text>
        </View>
        <Text style={styles.cardTitle}>{item.title}</Text>
        <Text style={styles.cardMeta}>
          {item.category.replace(/_/g, ' ')} · {item.landmark ? item.landmark + ' · ' : ''}
          {item.supporter_count === 0 ? 'no one has backed this yet' : `${item.supporter_count} neighbours back this`}
        </Text>
        <View style={styles.cardActionRow}>
          <TouchableOpacity style={[styles.actionBtn, { backgroundColor: Colors.lime }]} onPress={() => onToggleSupport(item.case_id)}>
            <Text style={styles.actionBtnText}>Back this</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionBtn, { backgroundColor: Colors.surface }]}>
            <Text style={styles.actionBtnText}>{item.status === 'assigned' ? 'Add a photo' : 'Still there'}</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    </View>
  );
}

export default function CommunityScreen() {
  const [activity, setActivity] = useState<ActivityItemWithExtras[]>([]);
  const [loading, setLoading] = useState(true);
  const [supportedCases, setSupportedCases] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setLoading(true);
    setTimeout(() => {
      setActivity(MOCK_COMMUNITY_ACTIVITY);
      setLoading(false);
    }, 500);
  }, []);

  const handleToggleSupport = (caseId: string) => {
    const isCurrentlySupported = !!supportedCases[caseId];
    setSupportedCases(prev => ({ ...prev, [caseId]: !isCurrentlySupported }));
    setActivity(prev => prev.map(item => {
      if (item.case_id === caseId) {
        return { ...item, supporter_count: item.supporter_count + (isCurrentlySupported ? -1 : 1) };
      }
      return item;
    }));
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.breadcrumb}>C10 • COMMUNITY</Text>
          <View style={styles.titleRow}>
            <Text style={styles.titleBack}>BACK WHAT'S</Text>
            <View style={{flex: 1}}/>
            <TouchableOpacity style={styles.notifBtn} onPress={() => {}}>
              <View style={styles.notifShadow} />
              <View style={styles.notifBtnInner}>
                <Text style={styles.notifIcon}>🔔</Text>
                <View style={styles.notifBadge} />
              </View>
            </TouchableOpacity>
          </View>
          <View style={styles.titleRealBadgeContainer}>
            <View style={styles.titleRealBadgeShadow} />
            <View style={styles.titleRealBadge}>
              <Text style={styles.titleRealText}>REAL</Text>
            </View>
          </View>
          <Text style={styles.subtitle}>
            Your support and photos help the city see what matters. No points, no leaderboards.
          </Text>
        </View>

        <View style={styles.filtersWrapper}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterList}>
            {CATEGORIES.map((cat, idx) => (
              <View key={cat} style={styles.filterItemContainer}>
                <View style={styles.filterItemShadow} />
                <TouchableOpacity style={[styles.filterItem, idx === 0 && { backgroundColor: Colors.lime }]} activeOpacity={0.8}>
                  <Text style={styles.filterItemText}>{cat}</Text>
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
            data={activity}
            keyExtractor={a => a.case_id}
            renderItem={({ item }) => <ActivityCard item={item} isSupported={!!supportedCases[item.case_id]} onToggleSupport={handleToggleSupport} />}
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
  titleBack: { fontSize: 42, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1 },
  titleRealBadgeContainer: { marginTop: -4, alignSelf: 'flex-start', marginBottom: Spacing[4] },
  titleRealBadgeShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.sm },
  titleRealBadge: { backgroundColor: Colors.ink, paddingHorizontal: Spacing[3], paddingVertical: 2, borderRadius: Radii.sm, borderWidth: 2, borderColor: Colors.surface },
  titleRealText: { color: Colors.lime, fontSize: 28, fontWeight: Typography.black, letterSpacing: -0.5 },
  subtitle: { fontSize: 15, color: Colors.muted, lineHeight: 22 },
  notifBtn: { width: 44, height: 44, marginTop: -20 },
  notifShadow: { position: 'absolute', top: 2, left: 2, width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.ink },
  notifBtnInner: { width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  notifIcon: { fontSize: 18 },
  notifBadge: { position: 'absolute', top: 8, right: 8, width: 10, height: 10, borderRadius: 5, backgroundColor: Colors.fire, borderWidth: 1.5, borderColor: Colors.ink },
  filtersWrapper: { marginBottom: Spacing[4] },
  filterList: { paddingHorizontal: Spacing[4], gap: Spacing[3] },
  filterItemContainer: { marginRight: Spacing[1] },
  filterItemShadow: { position: 'absolute', top: 3, left: 3, right: -3, bottom: -3, backgroundColor: Colors.ink, borderRadius: Radii.full },
  filterItem: { backgroundColor: Colors.surface, paddingHorizontal: Spacing[4], paddingVertical: Spacing[2], borderRadius: Radii.full, borderWidth: 1.5, borderColor: Colors.ink },
  filterItemText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  list: { paddingHorizontal: Spacing[4], paddingBottom: Layout.bottomNavHeight + Spacing[10] },
  cardContainer: { marginBottom: Spacing[4] },
  cardShadow: { position: 'absolute', top: 6, left: 6, right: -6, bottom: -6, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  card: { borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4] },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing[3] },
  statusPill: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  statusPillText: { fontSize: 12, fontWeight: Typography.bold },
  caseId: { fontFamily: 'monospace', fontSize: 12, color: Colors.muted },
  cardTitle: { fontSize: 20, fontWeight: Typography.bold, color: Colors.ink, marginBottom: Spacing[2], lineHeight: 26 },
  cardMeta: { fontSize: 14, color: Colors.muted, marginBottom: Spacing[4] },
  cardActionRow: { flexDirection: 'row', gap: Spacing[3] },
  actionBtn: { flex: 1, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, paddingVertical: Spacing[2], alignItems: 'center', justifyContent: 'center' },
  actionBtnText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  loadingBox: { paddingTop: Spacing[10], alignItems: 'center' },
});
