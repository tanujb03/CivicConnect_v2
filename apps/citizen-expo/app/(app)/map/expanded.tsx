/**
 * C12 — Expanded Map
 *
 * Full-screen map view with:
 * - Viewport-bounded API queries
 * - Department / Category filter pills
 * - Status filter pills (All, Submitted, In Progress, Resolved)
 * - Map marker legend (Submitted, In Progress, Resolved)
 * - Floating "Showing Issues" counter
 * - Interactive slide-up case preview drawer with image, landmark, upvotes & CTA
 * - Smooth fallback for web and devices without react-native-maps
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  FlatList,
  ActivityIndicator,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import {
  Colors,
  Typography,
  Spacing,
  Radii,
  Shadows,
  STATUS_LABELS,
  CATEGORY_ICONS,
  PRIORITY_COLORS,
} from '../../../src/constants/theme';
import { mapApi } from '../../../src/api/client';
import { MOCK_CASES } from '../../../src/data/mockData';
import type { MapCaseMarker, IssueCategory, CaseStatus } from '../../../src/types';

// Optional native map import
let MapView: any = null;
let Marker: any = null;
try {
  const Maps = require('react-native-maps');
  MapView = Maps.default;
  Marker = Maps.Marker;
} catch {
  // Graceful degradation when native map library is unlinked or on Web
}

interface MapMarkerWithDetails extends MapCaseMarker {
  image?: string;
  landmark?: string;
  created_at?: string;
  supporter_count?: number;
}

const DEPARTMENTS: { key: IssueCategory | 'all'; label: string; icon: string }[] = [
  { key: 'all', label: 'All Departments', icon: '🌐' },
  { key: 'roads', label: 'Roads', icon: '🛣️' },
  { key: 'sanitation', label: 'Sanitation', icon: '🗑️' },
  { key: 'water', label: 'Water', icon: '💧' },
  { key: 'lighting', label: 'Lighting', icon: '💡' },
  { key: 'drainage', label: 'Drainage', icon: '🌊' },
];

const STATUSES: { key: string; label: string }[] = [
  { key: 'all', label: 'All Status' },
  { key: 'submitted', label: 'Submitted' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'resolved', label: 'Resolved' },
];

function getStatusBadgeColor(status: string) {
  switch (status) {
    case 'submitted':
      return { bg: '#FEE2E2', text: '#B91C1C' };
    case 'in_progress':
    case 'assigned':
      return { bg: '#FEF3C7', text: '#B45309' };
    case 'resolved':
      return { bg: '#DCFCE7', text: '#15803D' };
    default:
      return { bg: Colors.neutral[100], text: Colors.neutral[700] };
  }
}

export default function ExpandedMapScreen() {
  const router = useRouter();
  const [hasMap] = useState(!!MapView);
  const [markers, setMarkers] = useState<MapMarkerWithDetails[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDepartment, setSelectedDepartment] = useState<IssueCategory | 'all'>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedCase, setSelectedCase] = useState<MapMarkerWithDetails | null>(null);

  // Fetch markers within bounded viewport
  const loadMarkers = useCallback(
    async (bounds = { north: 23.36, south: 23.32, east: 85.34, west: 85.28 }) => {
      setLoading(true);
      try {
        const filters: Record<string, string> = {};
        if (selectedDepartment !== 'all') filters.category = selectedDepartment;
        if (selectedStatus !== 'all') filters.status = selectedStatus;

        const data = await mapApi.getCasesInViewport(bounds, filters);
        // Enrich with mock details if missing
        const enriched = (data as MapMarkerWithDetails[]).map(m => {
          const match = MOCK_CASES.find(c => c.id === m.case_id);
          return {
            ...m,
            image: match?.evidence?.[0]?.url,
            landmark: match?.location?.landmark,
            created_at: match?.created_at,
            supporter_count: match?.supporter_count ?? m.supporter_count ?? 5,
          };
        });
        setMarkers(enriched);
      } catch {
        // Fallback to MOCK_CASES with full details
        const enriched: MapMarkerWithDetails[] = MOCK_CASES.map(c => ({
          case_id: c.id,
          case_number: c.case_number,
          lat: c.location.lat,
          lng: c.location.lng,
          category: c.category,
          priority: c.priority,
          status: c.status,
          title: c.title,
          supporter_count: c.supporter_count,
          image: c.evidence?.[0]?.url,
          landmark: c.location.landmark,
          created_at: c.created_at,
        }));
        setMarkers(enriched);
      } finally {
        setLoading(false);
      }
    },
    [selectedDepartment, selectedStatus]
  );

  useEffect(() => {
    loadMarkers();
  }, [loadMarkers]);

  // Client-side filtering
  const filteredMarkers = markers.filter(m => {
    const matchDept = selectedDepartment === 'all' || m.category === selectedDepartment;
    const matchStatus =
      selectedStatus === 'all' ||
      m.status === selectedStatus ||
      (selectedStatus === 'in_progress' && m.status === 'assigned');
    return matchDept && matchStatus;
  });

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ─── Top Header ─────────────────────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarMain}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => router.back()}
            accessibilityRole="button"
            accessibilityLabel="Back"
          >
            <Text style={styles.backBtnText}>‹ Back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>Issues Map</Text>
          <View style={{ width: 48 }} />
        </View>

        {/* Department Filters */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterScroll}
          style={styles.filterStrip}
        >
          {DEPARTMENTS.map(dept => {
            const isSelected = selectedDepartment === dept.key;
            return (
              <TouchableOpacity
                key={dept.key}
                style={[styles.filterChip, isSelected && styles.filterChipActive]}
                onPress={() => setSelectedDepartment(dept.key)}
              >
                <Text style={styles.filterChipIcon}>{dept.icon}</Text>
                <Text style={[styles.filterChipLabel, isSelected && styles.filterChipLabelActive]}>
                  {dept.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Status Filters */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterScroll}
          style={styles.statusFilterStrip}
        >
          {STATUSES.map(st => {
            const isSelected = selectedStatus === st.key;
            return (
              <TouchableOpacity
                key={st.key}
                style={[styles.statusChip, isSelected && styles.statusChipActive]}
                onPress={() => setSelectedStatus(st.key)}
              >
                <Text style={[styles.statusChipLabel, isSelected && styles.statusChipLabelActive]}>
                  {st.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* ─── Map Area ──────────────────────────────────────────── */}
      <View style={styles.mapArea}>
        {hasMap ? (
          <MapView
            style={styles.map}
            initialRegion={{
              latitude: 23.3441,
              longitude: 85.3096,
              latitudeDelta: 0.05,
              longitudeDelta: 0.05,
            }}
            onRegionChangeComplete={(region: any) => {
              loadMarkers({
                north: region.latitude + region.latitudeDelta / 2,
                south: region.latitude - region.latitudeDelta / 2,
                east: region.longitude + region.longitudeDelta / 2,
                west: region.longitude - region.longitudeDelta / 2,
              });
            }}
          >
            {filteredMarkers.map(m => {
              const badge = getStatusBadgeColor(m.status);
              return (
                <Marker
                  key={m.case_id}
                  coordinate={{ latitude: m.lat, longitude: m.lng }}
                  onPress={() => setSelectedCase(m)}
                >
                  <View style={[styles.markerBubble, { borderColor: badge.text }]}>
                    <Text style={styles.markerEmoji}>{CATEGORY_ICONS[m.category] ?? '📍'}</Text>
                  </View>
                </Marker>
              );
            })}
          </MapView>
        ) : (
          <View style={styles.listFallbackContainer}>
            <View style={styles.mapMockCanvas}>
              {filteredMarkers.map((m, idx) => {
                const badge = getStatusBadgeColor(m.status);
                // Spread markers visually across a simulated city grid
                const leftPercent = 15 + ((idx * 27) % 70);
                const topPercent = 15 + ((idx * 23) % 65);
                const isSelected = selectedCase?.case_id === m.case_id;

                return (
                  <TouchableOpacity
                    key={m.case_id}
                    style={[
                      styles.simulatedPin,
                      { left: `${leftPercent}%`, top: `${topPercent}%` },
                      isSelected && styles.simulatedPinSelected,
                    ]}
                    onPress={() => setSelectedCase(m)}
                  >
                    <View style={[styles.pinBubble, { borderColor: badge.text }]}>
                      <Text style={styles.pinIcon}>{CATEGORY_ICONS[m.category] ?? '📍'}</Text>
                    </View>
                    <View style={[styles.pinCallout, { backgroundColor: badge.text }]}>
                      <Text style={styles.pinCalloutText}>{m.case_number}</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* List Feed underneath simulated map */}
            <View style={styles.feedHeader}>
              <Text style={styles.feedHeaderText}>
                📍 Interactive Issues Feed ({filteredMarkers.length} in area)
              </Text>
            </View>

            <FlatList
              data={filteredMarkers}
              keyExtractor={item => item.case_id}
              contentContainerStyle={styles.caseListContainer}
              renderItem={({ item }) => {
                const badge = getStatusBadgeColor(item.status);
                const isSelected = selectedCase?.case_id === item.case_id;
                return (
                  <TouchableOpacity
                    style={[
                      styles.caseItemCard,
                      isSelected && styles.caseItemCardActive,
                    ]}
                    onPress={() => setSelectedCase(item)}
                  >
                    <View style={styles.caseItemHeader}>
                      <Text style={styles.caseItemIcon}>{CATEGORY_ICONS[item.category] ?? '📍'}</Text>
                      <View style={styles.caseItemTitleWrap}>
                        <View style={styles.caseTopLine}>
                          <Text style={styles.caseItemNumber}>{item.case_number}</Text>
                          <View style={[styles.miniStatusPill, { backgroundColor: badge.bg }]}>
                            <Text style={[styles.miniStatusText, { color: badge.text }]}>
                              {STATUS_LABELS[item.status] ?? item.status}
                            </Text>
                          </View>
                        </View>
                        <Text style={styles.caseItemTitle} numberOfLines={1}>
                          {item.title}
                        </Text>
                      </View>
                    </View>
                    {item.landmark && (
                      <Text style={styles.caseItemLandmark}>📍 {item.landmark}</Text>
                    )}
                  </TouchableOpacity>
                );
              }}
            />
          </View>
        )}

        {/* Floating Count Badge */}
        <View style={styles.floatingCountBadge}>
          <Text style={styles.floatingCountLabel}>Showing Issues</Text>
          <Text style={styles.floatingCountValue}>{filteredMarkers.length}</Text>
        </View>

        {loading && (
          <View style={styles.floatingLoader}>
            <ActivityIndicator size="small" color={Colors.brand[600]} />
            <Text style={styles.loaderText}>Updating map...</Text>
          </View>
        )}
      </View>

      {/* ─── Status Legend ─────────────────────────────────────── */}
      <View style={styles.legendContainer}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#DC2626' }]} />
          <Text style={styles.legendText}>Submitted</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#D97706' }]} />
          <Text style={styles.legendText}>In Progress</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#16A34A' }]} />
          <Text style={styles.legendText}>Resolved</Text>
        </View>
      </View>

      {/* ─── Case Detail Bottom Drawer ─────────────────────────── */}
      {selectedCase && (
        <View style={styles.drawer}>
          <View style={styles.drawerHandle} />
          <View style={styles.drawerHeader}>
            <View style={styles.drawerTitleRow}>
              <View style={styles.categoryCircle}>
                <Text style={styles.drawerEmoji}>{CATEGORY_ICONS[selectedCase.category] ?? '📍'}</Text>
              </View>
              <View style={styles.drawerTextWrap}>
                <Text style={styles.drawerTitle} numberOfLines={1}>
                  {selectedCase.title}
                </Text>
                <Text style={styles.drawerCategoryText}>
                  {selectedCase.category.toUpperCase()} • {selectedCase.case_number}
                </Text>
              </View>
            </View>
            <TouchableOpacity onPress={() => setSelectedCase(null)} style={styles.closeDrawerBtn}>
              <Text style={styles.closeDrawerText}>✕</Text>
            </TouchableOpacity>
          </View>

          {selectedCase.image && (
            <Image
              source={{ uri: selectedCase.image }}
              style={styles.drawerImage}
              resizeMode="cover"
            />
          )}

          <View style={styles.detailGrid}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Status</Text>
              <View
                style={[
                  styles.statusBadgePill,
                  { backgroundColor: getStatusBadgeColor(selectedCase.status).bg },
                ]}
              >
                <Text
                  style={[
                    styles.statusBadgeText,
                    { color: getStatusBadgeColor(selectedCase.status).text },
                  ]}
                >
                  {STATUS_LABELS[selectedCase.status] ?? selectedCase.status}
                </Text>
              </View>
            </View>

            {selectedCase.landmark && (
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Landmark</Text>
                <Text style={styles.detailValue}>{selectedCase.landmark}</Text>
              </View>
            )}

            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Upvotes / Support</Text>
              <Text style={styles.detailValue}>
                👥 {selectedCase.supporter_count ?? 12} Citizens
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={styles.openCaseBtn}
            onPress={() => router.push(`/(app)/case/${selectedCase.case_id}`)}
          >
            <Text style={styles.openCaseBtnText}>View Details →</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  topBar: {
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
    zIndex: 10,
    ...Shadows.sm,
  },
  topBarMain: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backBtn: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  backBtnText: {
    fontSize: Typography.bodyLarge.fontSize,
    color: Colors.brand[600],
    fontWeight: '700',
  },
  topBarTitle: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  filterStrip: {
    paddingVertical: Spacing.xs,
  },
  statusFilterStrip: {
    paddingVertical: 6,
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[100],
  },
  filterScroll: {
    paddingHorizontal: Spacing.md,
    gap: Spacing.xs,
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[100],
    borderWidth: 1,
    borderColor: Colors.neutral[200],
  },
  filterChipActive: {
    backgroundColor: Colors.brand[600],
    borderColor: Colors.brand[600],
  },
  filterChipIcon: {
    fontSize: 14,
  },
  filterChipLabel: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[700],
    fontWeight: '500',
  },
  filterChipLabelActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  statusChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 5,
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[100],
  },
  statusChipActive: {
    backgroundColor: '#3B82F6',
  },
  statusChipLabel: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[600],
    fontWeight: '500',
  },
  statusChipLabelActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  mapArea: {
    flex: 1,
    position: 'relative',
  },
  map: {
    ...StyleSheet.absoluteFillObject,
  },
  markerBubble: {
    backgroundColor: '#FFFFFF',
    padding: 6,
    borderRadius: Radii.full,
    borderWidth: 2,
    ...Shadows.md,
  },
  markerEmoji: {
    fontSize: 18,
  },
  listFallbackContainer: {
    flex: 1,
    backgroundColor: '#F1F5F9',
  },
  mapMockCanvas: {
    height: 180,
    backgroundColor: '#E2E8F0',
    position: 'relative',
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[300],
    overflow: 'hidden',
  },
  simulatedPin: {
    position: 'absolute',
    alignItems: 'center',
    transform: [{ translateX: -15 }, { translateY: -20 }],
  },
  simulatedPinSelected: {
    transform: [{ scale: 1.2 }, { translateX: -15 }, { translateY: -20 }],
    zIndex: 10,
  },
  pinBubble: {
    backgroundColor: '#FFFFFF',
    padding: 5,
    borderRadius: Radii.full,
    borderWidth: 2,
    ...Shadows.sm,
  },
  pinIcon: {
    fontSize: 14,
  },
  pinCallout: {
    borderRadius: 4,
    paddingHorizontal: 4,
    paddingVertical: 1,
    marginTop: 2,
  },
  pinCalloutText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '700',
  },
  feedHeader: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
  },
  feedHeaderText: {
    fontSize: Typography.labelMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[800],
  },
  caseListContainer: {
    padding: Spacing.md,
    gap: Spacing.sm,
    paddingBottom: 80,
  },
  caseItemCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.xs,
    ...Shadows.sm,
  },
  caseItemCardActive: {
    borderColor: Colors.brand[600],
    backgroundColor: Colors.brand[50] + '30',
  },
  caseItemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  caseItemIcon: {
    fontSize: 20,
  },
  caseItemTitleWrap: {
    flex: 1,
    gap: 2,
  },
  caseTopLine: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  caseItemNumber: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: Colors.brand[700],
  },
  miniStatusPill: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: Radii.full,
  },
  miniStatusText: {
    fontSize: 10,
    fontWeight: '700',
  },
  caseItemTitle: {
    fontSize: Typography.bodyMedium.fontSize,
    fontWeight: '600',
    color: Colors.neutral[900],
  },
  caseItemLandmark: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[500],
    marginLeft: 28,
  },
  floatingCountBadge: {
    position: 'absolute',
    top: Spacing.md,
    right: Spacing.md,
    backgroundColor: '#FFFFFFEE',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radii.md,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    alignItems: 'center',
    ...Shadows.md,
  },
  floatingCountLabel: {
    fontSize: 10,
    color: Colors.neutral[500],
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  floatingCountValue: {
    fontSize: 16,
    fontWeight: '800',
    color: Colors.neutral[900],
  },
  floatingLoader: {
    position: 'absolute',
    top: Spacing.md,
    left: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: '#FFFFFFEE',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    ...Shadows.sm,
  },
  loaderText: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[700],
  },
  legendContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: Spacing.lg,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface,
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[200],
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendText: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[600],
    fontWeight: '600',
  },
  drawer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radii.xl,
    borderTopRightRadius: Radii.xl,
    padding: Spacing.lg,
    paddingBottom: Spacing.xl,
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[200],
    gap: Spacing.sm,
    ...Shadows.lg,
  },
  drawerHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.neutral[300],
    alignSelf: 'center',
    marginBottom: 4,
  },
  drawerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  drawerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    flex: 1,
  },
  categoryCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.brand[50],
    justifyContent: 'center',
    alignItems: 'center',
  },
  drawerEmoji: {
    fontSize: 22,
  },
  drawerTextWrap: {
    flex: 1,
    gap: 2,
  },
  drawerTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  drawerCategoryText: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[500],
    fontWeight: '600',
  },
  closeDrawerBtn: {
    padding: Spacing.xs,
  },
  closeDrawerText: {
    fontSize: 18,
    color: Colors.neutral[400],
    fontWeight: '700',
  },
  drawerImage: {
    width: '100%',
    height: 140,
    borderRadius: Radii.md,
    marginTop: Spacing.xs,
  },
  detailGrid: {
    gap: Spacing.xs,
    marginVertical: Spacing.xs,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 2,
  },
  detailLabel: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[500],
    fontWeight: '500',
  },
  detailValue: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[800],
    fontWeight: '600',
  },
  statusBadgePill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: Radii.full,
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  openCaseBtn: {
    backgroundColor: Colors.brand[600],
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    alignItems: 'center',
    marginTop: Spacing.xs,
  },
  openCaseBtnText: {
    color: '#FFFFFF',
    fontSize: Typography.labelMedium.fontSize,
    fontWeight: '700',
  },
});
