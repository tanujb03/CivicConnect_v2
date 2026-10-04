/**
 * C11 — City Map View
 *
 * Interactive map of civic cases with:
 * - Category filter pills (All, Roads, Sanitation, Water, Lighting)
 * - Map layer pins color-coded by status (Red=Submitted, Amber=In Progress, Green=Resolved)
 * - Pin selection drawer showing case details & quick link to case
 * - Fallback interactive canvas for Web and Expo Go environments
 * - Deep link to Full Map Explorer
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Dimensions,
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
  PRIORITY_LABELS,
} from '../../../src/constants/theme';
import { mapApi } from '../../../src/api/client';
import { MOCK_CASES } from '../../../src/data/mockData';
import type { MapCaseMarker, IssueCategory } from '../../../src/types';

// Map is conditionally imported so the app boots in Expo Go / Web
let MapView: any = null;
let Marker: any = null;
try {
  const Maps = require('react-native-maps');
  MapView = Maps.default;
  Marker = Maps.Marker;
} catch {
  // Graceful degradation when react-native-maps is not natively compiled
}

const CATEGORIES: { key: string; label: string; icon: string }[] = [
  { key: 'all', label: 'All Issues', icon: '🌐' },
  { key: 'roads', label: 'Roads', icon: '🛣️' },
  { key: 'sanitation', label: 'Sanitation', icon: '🗑️' },
  { key: 'water', label: 'Water', icon: '💧' },
  { key: 'lighting', label: 'Lighting', icon: '💡' },
];

export default function MapScreen() {
  const router = useRouter();
  const [markers, setMarkers] = useState<MapCaseMarker[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedMarker, setSelectedMarker] = useState<MapCaseMarker | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasNativeMap] = useState(!!MapView);

  const loadMarkers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await mapApi.getCasesInViewport({
        north: 23.36, south: 23.32, east: 85.33, west: 85.29,
      });
      setMarkers(data);
    } catch {
      setMarkers(
        MOCK_CASES.map(c => ({
          case_id: c.id,
          case_number: c.case_number,
          title: c.title,
          lat: c.location.lat,
          lng: c.location.lng,
          category: c.category,
          priority: c.priority,
          status: c.status,
        }))
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMarkers();
  }, [loadMarkers]);

  const filteredMarkers = selectedCategory === 'all'
    ? markers
    : markers.filter(m => m.category === selectedCategory);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ─── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View style={styles.headerTitleRow}>
            <View style={styles.headerIconBox}>
              <Text style={styles.headerIcon}>🗺️</Text>
            </View>
            <View>
              <Text style={styles.headerTitle}>City Map</Text>
              <Text style={styles.headerSub}>Civic issues in Ranchi</Text>
            </View>
          </View>

          <TouchableOpacity
            style={styles.expandBtn}
            onPress={() => router.push('/(app)/map/expanded')}
          >
            <Text style={styles.expandBtnText}>Full Explorer ↗</Text>
          </TouchableOpacity>
        </View>

        {/* Category Filter Pills */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {CATEGORIES.map(cat => {
            const isSelected = selectedCategory === cat.key;
            return (
              <TouchableOpacity
                key={cat.key}
                style={[styles.filterPill, isSelected && styles.filterPillActive]}
                onPress={() => {
                  setSelectedCategory(cat.key);
                  setSelectedMarker(null);
                }}
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

      {/* ─── Map Canvas ──────────────────────────────────────── */}
      <View style={styles.mapContainer}>
        {loading && (
          <View style={styles.loaderBox}>
            <ActivityIndicator size="small" color="#0D4A1A" />
          </View>
        )}

        {hasNativeMap ? (
          <MapView
            style={styles.nativeMap}
            initialRegion={{
              latitude: 23.3441,
              longitude: 85.3096,
              latitudeDelta: 0.05,
              longitudeDelta: 0.05,
            }}
          >
            {filteredMarkers.map(m => (
              <Marker
                key={m.case_id}
                coordinate={{ latitude: m.lat, longitude: m.lng }}
                title={m.case_number}
                description={m.title}
                onPress={() => setSelectedMarker(m)}
              />
            ))}
          </MapView>
        ) : (
          /* Interactive Web/Mobile Fallback Canvas */
          <View style={styles.interactiveCanvas}>
            <View style={styles.canvasTerrain}>
              <View style={styles.roadH1} />
              <View style={styles.roadH2} />
              <View style={styles.roadV1} />
              <View style={styles.roadV2} />
              <View style={styles.river} />
              <View style={styles.parkZone}>
                <Text style={styles.parkZoneText}>🌲 Morabadi Park</Text>
              </View>
            </View>

            {filteredMarkers.map((m, idx) => {
              const isSelected = selectedMarker?.case_id === m.case_id;
              const statusBg =
                m.status === 'resolved'
                  ? '#15803D'
                  : m.status === 'in_progress'
                  ? '#D97706'
                  : '#B91C1C';
              // Distribute markers across canvas coordinates
              const left = 50 + ((idx * 80 + 30) % 270);
              const top = 60 + ((idx * 60 + 20) % 200);

              return (
                <TouchableOpacity
                  key={m.case_id}
                  style={[
                    styles.pin,
                    { left, top, backgroundColor: statusBg },
                    isSelected && styles.pinSelected,
                  ]}
                  onPress={() => setSelectedMarker(m)}
                >
                  <Text style={styles.pinIcon}>{CATEGORY_ICONS[m.category] ?? '📍'}</Text>
                </TouchableOpacity>
              );
            })}

            <View style={styles.canvasLegend}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#B91C1C' }]} />
                <Text style={styles.legendText}>Submitted</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#D97706' }]} />
                <Text style={styles.legendText}>In Progress</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#15803D' }]} />
                <Text style={styles.legendText}>Resolved</Text>
              </View>
            </View>
          </View>
        )}
      </View>

      {/* ─── Selected Case Bottom Drawer / Preview ───────────── */}
      {selectedMarker ? (
        <View style={styles.detailDrawer}>
          <View style={styles.drawerTop}>
            <View>
              <Text style={styles.drawerCaseNum}>{selectedMarker.case_number}</Text>
              <Text style={styles.drawerTitle} numberOfLines={1}>{selectedMarker.title}</Text>
            </View>
            <TouchableOpacity onPress={() => setSelectedMarker(null)}>
              <Text style={styles.drawerClose}>✕</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.drawerMeta}>
            <Text style={styles.drawerCategory}>
              {CATEGORY_ICONS[selectedMarker.category] ?? '⚠️'} {selectedMarker.category}
            </Text>
            <Text style={styles.drawerStatus}>
              Status: {STATUS_LABELS[selectedMarker.status] ?? selectedMarker.status}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.drawerBtn}
            onPress={() => router.push(`/(app)/case/${selectedMarker.case_id}`)}
          >
            <Text style={styles.drawerBtnText}>View Full Case Details →</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.hintBox}>
          <Text style={styles.hintText}>
            📍 Tap any colored marker on the map to inspect issue details
          </Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAF9' },
  header: {
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[3],
    backgroundColor: '#0D4A1A',
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[3],
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3],
  },
  headerIconBox: {
    width: 38,
    height: 38,
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
  },
  expandBtn: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
  },
  expandBtnText: {
    color: '#fff',
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
  },

  filterRow: {
    gap: Spacing[2],
    paddingBottom: Spacing[1],
  },
  filterPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
    borderRadius: Radii.full,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  filterPillActive: { backgroundColor: '#10B981' },
  filterPillIcon: { fontSize: 12 },
  filterPillText: {
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    color: 'rgba(255,255,255,0.8)',
  },
  filterPillTextActive: { color: '#fff', fontWeight: Typography.bold },

  mapContainer: { flex: 1, position: 'relative' },
  nativeMap: { flex: 1 },
  loaderBox: {
    position: 'absolute',
    top: 15,
    right: 15,
    backgroundColor: '#fff',
    borderRadius: Radii.full,
    padding: Spacing[2],
    zIndex: 10,
    ...Shadows.sm,
  },

  // Interactive Fallback Canvas
  interactiveCanvas: {
    flex: 1,
    backgroundColor: '#E6EFE9',
    position: 'relative',
    overflow: 'hidden',
  },
  canvasTerrain: { ...StyleSheet.absoluteFillObject },
  roadH1: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 100,
    height: 18,
    backgroundColor: '#CBD5E1',
  },
  roadH2: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 240,
    height: 16,
    backgroundColor: '#CBD5E1',
  },
  roadV1: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 120,
    width: 18,
    backgroundColor: '#CBD5E1',
  },
  roadV2: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 270,
    width: 16,
    backgroundColor: '#CBD5E1',
  },
  river: {
    position: 'absolute',
    top: 310,
    left: 0,
    right: 0,
    height: 30,
    backgroundColor: '#BAE6FD',
  },
  parkZone: {
    position: 'absolute',
    top: 20,
    right: 20,
    backgroundColor: '#DCFCE7',
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[2],
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: '#86EFAC',
  },
  parkZoneText: { fontSize: 10, color: '#166534', fontWeight: Typography.bold },

  pin: {
    position: 'absolute',
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
    ...Shadows.md,
  },
  pinSelected: {
    transform: [{ scale: 1.35 }],
    borderColor: '#FEF08A',
    zIndex: 20,
  },
  pinIcon: { fontSize: 18 },

  canvasLegend: {
    position: 'absolute',
    bottom: 15,
    left: 15,
    backgroundColor: 'rgba(255,255,255,0.92)',
    borderRadius: Radii.lg,
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[2],
    flexDirection: 'row',
    gap: Spacing[3],
    ...Shadows.sm,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { fontSize: 10, fontWeight: Typography.bold, color: Colors.neutral[700] },

  // Detail Drawer
  detailDrawer: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: Spacing[5],
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[200],
    ...Shadows.lg,
  },
  drawerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[2],
  },
  drawerCaseNum: {
    fontSize: 11,
    fontWeight: Typography.bold,
    color: Colors.neutral[400],
    letterSpacing: 0.5,
  },
  drawerTitle: {
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    maxWidth: 280,
  },
  drawerClose: { fontSize: 18, color: Colors.neutral[400], padding: 4 },
  drawerMeta: {
    flexDirection: 'row',
    gap: Spacing[3],
    marginBottom: Spacing[4],
  },
  drawerCategory: {
    fontSize: Typography.xs,
    color: Colors.neutral[600],
    textTransform: 'capitalize',
  },
  drawerStatus: {
    fontSize: Typography.xs,
    color: '#059669',
    fontWeight: Typography.semibold,
  },
  drawerBtn: {
    backgroundColor: '#0D4A1A',
    borderRadius: Radii.xl,
    paddingVertical: Spacing[3],
    alignItems: 'center',
  },
  drawerBtnText: {
    color: '#fff',
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
  },

  hintBox: {
    backgroundColor: '#fff',
    paddingVertical: Spacing[3],
    paddingHorizontal: Spacing[5],
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[200],
  },
  hintText: {
    fontSize: 11,
    color: Colors.neutral[500],
    textAlign: 'center',
  },
});
