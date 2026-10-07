import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../../src/constants/theme';
import { MOCK_CASES } from '../../../src/data/mockData';
import type { CivicCase } from '../../../src/types';

function StatusBadge({ status }: { status: string }) {
  const getStatusConfig = (s: string) => {
    switch(s) {
      case 'verification_requested':
        return { label: 'Awaiting you', bg: Colors.amber, color: Colors.ink, border: true };
      default:
        return { label: s.replace(/_/g, ' ').toUpperCase(), bg: Colors.surface, color: Colors.ink, border: true };
    }
  };
  const c = getStatusConfig(status);
  return (
    <View style={[styles.statusBadge, { backgroundColor: c.bg }, c.border && { borderWidth: 1.5, borderColor: Colors.ink }]}>
      <Text style={[styles.statusText, { color: c.color }]}>{c.label}</Text>
    </View>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const getPriorityConfig = (p: string) => {
    switch(p) {
      case 'critical': return { label: 'URGENT', bg: Colors.fire, color: Colors.surface };
      default: return { label: p.toUpperCase(), bg: Colors.surface, color: Colors.ink, border: true };
    }
  };
  const c = getPriorityConfig(priority);
  return (
    <View style={[styles.priorityBadge, { backgroundColor: c.bg }, c.border && { borderWidth: 1.5, borderColor: Colors.ink }]}>
      <Text style={[styles.priorityText, { color: c.color }]}>{c.label}</Text>
    </View>
  );
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <View style={[styles.categoryBadge, { borderWidth: 1.5, borderColor: Colors.ink }]}>
      <Text style={styles.categoryText}>{category.replace(/_/g, ' ')}</Text>
    </View>
  );
}

export default function CaseDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [caseData, setCaseData] = useState<CivicCase | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setTimeout(() => {
      let c = MOCK_CASES.find(x => x.id === id || x.case_number === id);
      if (!c) c = MOCK_CASES.find(x => x.status === 'verification_requested') || MOCK_CASES[0];
      setCaseData(c);
      setLoading(false);
    }, 300);
  }, [id]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={Colors.ink} />
        </View>
      </SafeAreaView>
    );
  }

  const c = caseData!;
  const isVerification = c.status === 'verification_requested';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{c.case_number}</Text>
        <TouchableOpacity style={styles.shareBtn}>
          <Text style={styles.shareBtnText}>🔗</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.titleSection}>
          <Text style={styles.mainTitle}>{c.title.toUpperCase()}</Text>
          <View style={styles.badgeRow}>
            <PriorityBadge priority={c.priority} />
            <StatusBadge status={c.status} />
            <CategoryBadge category={c.category} />
          </View>
        </View>

        <View style={styles.photoGrid}>
          <View style={styles.photoContainer}>
            <View style={styles.photoShadow} />
            <View style={[styles.photoFrame, { backgroundColor: '#E2E8F0' }]}>
              <View style={styles.photoLabel}>
                <Text style={styles.photoLabelText}>Your photo</Text>
              </View>
            </View>
          </View>
          <View style={styles.photoContainer}>
            <View style={styles.photoShadow} />
            <View style={[styles.photoFrame, { backgroundColor: '#E2E8F0' }]}>
              <View style={[styles.photoLabel, { backgroundColor: Colors.lime }]}>
                <Text style={styles.photoLabelText}>After photo</Text>
              </View>
            </View>
          </View>
        </View>

        <View style={styles.locationContainer}>
          <View style={styles.locationShadow} />
          <View style={styles.locationFrame}>
            <Text style={styles.locationLabel}>WHERE IT'S AT</Text>
            <Text style={styles.locationText}>{c.location.landmark || 'Main Road, Ranchi'}</Text>
          </View>
        </View>
      </ScrollView>

      {isVerification && (
        <View style={styles.bottomSheetContainer}>
          <View style={styles.handle} />
          <Text style={styles.sheetTitle}>IS IT FIXED?</Text>
          <Text style={styles.sheetSub}>
            The team says the cover is on and the area is barricaded. Only you can confirm.
          </Text>

          <TouchableOpacity style={[styles.optionBtn, { backgroundColor: Colors.lime }]}>
            <View style={styles.radioSelected} />
            <Text style={styles.optionText}>Yes, it's fixed</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.optionBtn}>
            <View style={styles.radioEmpty} />
            <Text style={styles.optionText}>Partly fixed</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.optionBtn}>
            <View style={styles.radioEmpty} />
            <View>
              <Text style={styles.optionText}>It's still happening</Text>
              <Text style={styles.optionSubText}>We'll reopen the case</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity style={styles.optionBtn}>
            <View style={styles.radioEmpty} />
            <Text style={styles.optionText}>No, nothing was done</Text>
          </TouchableOpacity>

          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.addPhotoBtn}>
              <Text style={styles.addPhotoText}>Add photo</Text>
            </TouchableOpacity>
            
            <View style={styles.sendBtnContainer}>
              <View style={styles.sendBtnShadow} />
              <TouchableOpacity style={styles.sendBtn}>
                <Text style={styles.sendBtnText}>Send answer</Text>
                <View style={styles.sendBtnArrow}>
                  <Text style={styles.sendBtnArrowText}>→</Text>
                </View>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4] },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  shareBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  shareBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontFamily: 'monospace', fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  scrollContent: { paddingBottom: Spacing[12] },
  titleSection: { paddingHorizontal: Spacing[4], marginBottom: Spacing[4] },
  mainTitle: { fontSize: 32, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1, lineHeight: 34, marginBottom: Spacing[3] },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing[2] },
  statusBadge: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  statusText: { fontSize: 12, fontWeight: Typography.bold },
  priorityBadge: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  priorityText: { fontSize: 12, fontWeight: Typography.bold },
  categoryBadge: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full, backgroundColor: Colors.surface },
  categoryText: { fontSize: 12, fontWeight: Typography.bold, color: Colors.ink },
  photoGrid: { flexDirection: 'row', paddingHorizontal: Spacing[4], gap: Spacing[3], marginBottom: Spacing[4] },
  photoContainer: { flex: 1, aspectRatio: 1 },
  photoShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.dot, borderRadius: Radii.lg },
  photoFrame: { flex: 1, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[2], justifyContent: 'flex-end', alignItems: 'flex-start' },
  photoLabel: { backgroundColor: Colors.surface, borderWidth: 1.5, borderColor: Colors.ink, borderRadius: Radii.full, paddingHorizontal: Spacing[2], paddingVertical: 2 },
  photoLabelText: { fontSize: 10, fontWeight: Typography.bold, color: Colors.ink },
  locationContainer: { marginHorizontal: Spacing[4], marginBottom: Spacing[6] },
  locationShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  locationFrame: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4] },
  locationLabel: { fontFamily: 'monospace', fontSize: 10, fontWeight: Typography.bold, color: Colors.ink, marginBottom: 4 },
  locationText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  bottomSheetContainer: { position: 'absolute', bottom: 0, left: 0, right: 0, backgroundColor: Colors.surface, borderTopLeftRadius: Radii['2xl'], borderTopRightRadius: Radii['2xl'], borderTopWidth: 4, borderRightWidth: 4, borderLeftWidth: 4, borderColor: Colors.ink, padding: Spacing[5], paddingBottom: Spacing[10] },
  handle: { width: 40, height: 6, backgroundColor: Colors.ink, borderRadius: 3, alignSelf: 'center', marginBottom: Spacing[4] },
  sheetTitle: { fontSize: 24, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -0.5, marginBottom: Spacing[2] },
  sheetSub: { fontSize: 14, color: Colors.muted, marginBottom: Spacing[4], lineHeight: 20 },
  optionBtn: { flexDirection: 'row', alignItems: 'center', borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], marginBottom: Spacing[3] },
  radioEmpty: { width: 16, height: 16, borderRadius: 8, borderWidth: 2, borderColor: Colors.ink, marginRight: Spacing[3] },
  radioSelected: { width: 16, height: 16, borderRadius: 8, borderWidth: 5, borderColor: Colors.ink, marginRight: Spacing[3] },
  optionText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  optionSubText: { fontSize: 12, color: Colors.muted, marginTop: 2 },
  actionRow: { flexDirection: 'row', gap: Spacing[3], marginTop: Spacing[2] },
  addPhotoBtn: { flex: 1, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, alignItems: 'center', justifyContent: 'center' },
  addPhotoText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  sendBtnContainer: { flex: 1.5 },
  sendBtnShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  sendBtn: { backgroundColor: Colors.lime, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing[3], paddingHorizontal: Spacing[4] },
  sendBtnText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  sendBtnArrow: { width: 28, height: 28, borderRadius: 14, backgroundColor: Colors.fire, alignItems: 'center', justifyContent: 'center' },
  sendBtnArrowText: { color: Colors.surface, fontWeight: Typography.bold },
  loadingBox: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
