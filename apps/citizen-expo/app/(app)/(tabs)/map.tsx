/**
 * C11 — City Map View
 * Real interactive map using OpenStreetMap tiles via Leaflet.
 * - On native (APK): uses react-native-webview
 * - On web: uses an iframe
 */
import React, { useState, useEffect, useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, STATUS_LABELS, CATEGORY_ICONS, Layout } from '../../../src/constants/theme';
import { MOCK_CASES } from '../../../src/data/mockData';

// Conditionally import WebView only on native
let WebView: any = null;
if (Platform.OS !== 'web') {
  try {
    WebView = require('react-native-webview').WebView;
  } catch (e) {
    // WebView not available
  }
}

interface MapMarker {
  case_id: string;
  case_number: string;
  title: string;
  lat: number;
  lng: number;
  category: string;
  priority: string;
  status: string;
}

const CATEGORIES = [
  { key: 'all', label: 'All', icon: '🌐' },
  { key: 'roads', label: 'Roads', icon: '🛣️' },
  { key: 'sanitation', label: 'Sanitation', icon: '🗑️' },
  { key: 'water', label: 'Water', icon: '💧' },
  { key: 'lighting', label: 'Lighting', icon: '💡' },
];

function getStatusColor(status: string): string {
  if (status === 'resolved') return '#22c55e';
  if (status === 'in_progress' || status === 'assigned') return '#f59e0b';
  if (status === 'verification_requested') return '#3b82f6';
  return '#ef4444';
}

function buildMapHTML(markers: MapMarker[]): string {
  const escapedMarkers = markers.map(m => ({
    ...m,
    title: m.title.replace(/'/g, "\\'").replace(/"/g, '&quot;'),
  }));

  const pins = escapedMarkers.map(m => {
    const color = getStatusColor(m.status);
    const statusLabel = STATUS_LABELS[m.status] || m.status;
    return `
      L.circleMarker([${m.lat}, ${m.lng}], {
        radius: 14,
        fillColor: '${color}',
        color: '#161616',
        weight: 3,
        opacity: 1,
        fillOpacity: 0.9
      }).addTo(map)
        .bindPopup('<div style="font-family:sans-serif;min-width:160px"><b style="font-size:14px">${m.title}</b><br><span style="font-size:11px;color:#888">${m.case_number}</span><br><span style="color:${color};font-weight:bold;font-size:12px">${statusLabel}</span><br><button onclick="window.selectCase(\\'${m.case_id}\\',\\'${m.case_number}\\',\\'${m.title}\\',\\'${m.status}\\')" style="margin-top:6px;padding:6px 12px;background:#161616;color:#C8FF2E;border:none;border-radius:8px;font-weight:bold;cursor:pointer;font-size:12px">View Case →</button></div>', {maxWidth: 220});
    `;
  }).join('\n');

  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body, #map { width: 100%; height: 100%; }
  .leaflet-control-attribution { font-size: 9px !important; }
</style>
</head>
<body>
<div id="map"></div>
<script>
  var map = L.map('map', {
    zoomControl: false,
    attributionControl: true
  }).setView([23.3441, 85.3096], 14);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
  }).addTo(map);

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  window.selectCase = function(caseId, caseNumber, title, status) {
    try {
      if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(JSON.stringify({type:'pin', caseId: caseId}));
      }
    } catch(e) {}
  };

  ${pins}
</script>
</body>
</html>`;
}

export default function MapScreen() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedMarker, setSelectedMarker] = useState<any>(null);
  const [mapReady, setMapReady] = useState(false);

  const markers: MapMarker[] = useMemo(() => 
    MOCK_CASES.map(c => ({
      case_id: c.id,
      case_number: c.case_number,
      title: c.title,
      lat: c.location.lat,
      lng: c.location.lng,
      category: c.category,
      priority: c.priority,
      status: c.status,
    })), []);

  const filtered = selectedCategory === 'all' ? markers : markers.filter(m => m.category === selectedCategory);
  const mapHTML = useMemo(() => buildMapHTML(filtered), [filtered]);

  const handleWebViewMessage = (event: any) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'pin') {
        router.push(`/(app)/case/${data.caseId}`);
      }
    } catch {}
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🗺️ City Map</Text>
        <Text style={styles.headerSub}>CivicConnect • Ranchi</Text>
      </View>

      {/* Category Filters */}
      <View style={styles.filtersWrapper}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterList}>
          {CATEGORIES.map(cat => (
            <TouchableOpacity
              key={cat.key}
              style={[styles.filterChip, selectedCategory === cat.key && styles.filterChipActive]}
              onPress={() => setSelectedCategory(cat.key)}
              activeOpacity={0.8}
            >
              <Text style={styles.filterText}>{cat.icon} {cat.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Map Container */}
      <View style={styles.mapContainer}>
        {Platform.OS === 'web' ? (
          // WEB: Use iframe with srcdoc
          <iframe
            srcDoc={mapHTML}
            style={{ width: '100%', height: '100%', border: 'none' } as any}
          />
        ) : WebView ? (
          // NATIVE (APK): Use WebView
          <WebView
            source={{ html: mapHTML }}
            style={{ flex: 1 }}
            onMessage={handleWebViewMessage}
            javaScriptEnabled={true}
            domStorageEnabled={true}
            originWhitelist={['*']}
            onLoadEnd={() => setMapReady(true)}
            mixedContentMode="always"
          />
        ) : (
          // FALLBACK: No map available
          <View style={styles.fallback}>
            <Text style={styles.fallbackEmoji}>🗺️</Text>
            <Text style={styles.fallbackTitle}>Map Loading...</Text>
            <Text style={styles.fallbackSub}>Install react-native-webview for full map support</Text>
          </View>
        )}
      </View>

      {/* Legend */}
      <View style={styles.legendRow}>
        <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#ef4444' }]} /><Text style={styles.legendText}>New</Text></View>
        <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#f59e0b' }]} /><Text style={styles.legendText}>Working</Text></View>
        <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#3b82f6' }]} /><Text style={styles.legendText}>Verify</Text></View>
        <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#22c55e' }]} /><Text style={styles.legendText}>Fixed</Text></View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { paddingHorizontal: Spacing[4], paddingTop: Spacing[3], paddingBottom: Spacing[2] },
  headerTitle: { fontSize: 22, fontWeight: Typography.black, color: Colors.ink },
  headerSub: { fontSize: 12, color: Colors.muted, fontWeight: Typography.bold },
  filtersWrapper: { paddingBottom: Spacing[2] },
  filterList: { paddingHorizontal: Spacing[4], gap: Spacing[2] },
  filterChip: { backgroundColor: Colors.surface, paddingHorizontal: Spacing[3], paddingVertical: Spacing[2], borderRadius: Radii.full, borderWidth: 2, borderColor: Colors.ink },
  filterChipActive: { backgroundColor: Colors.lime },
  filterText: { fontSize: 13, fontWeight: Typography.bold, color: Colors.ink },
  mapContainer: { flex: 1, marginHorizontal: Spacing[4], borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, overflow: 'hidden', marginBottom: Spacing[2] },
  legendRow: { flexDirection: 'row', justifyContent: 'center', gap: Spacing[4], paddingVertical: Spacing[2], paddingBottom: Spacing[3] },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 10, height: 10, borderRadius: 5, borderWidth: 1.5, borderColor: Colors.ink },
  legendText: { fontSize: 11, fontWeight: Typography.bold, color: Colors.ink },
  fallback: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.ground },
  fallbackEmoji: { fontSize: 48, marginBottom: Spacing[3] },
  fallbackTitle: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink },
  fallbackSub: { fontSize: 13, color: Colors.muted, marginTop: Spacing[1] },
});
