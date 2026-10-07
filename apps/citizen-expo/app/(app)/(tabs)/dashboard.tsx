import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';
import { MOCK_CASES, MOCK_USER } from '../../../src/data/mockData';

export default function DashboardScreen() {
  const router = useRouter();
  const verificationCase = MOCK_CASES.find(c => c.status === 'verification_requested') || MOCK_CASES[0];
  const inProgressCase = MOCK_CASES.find(c => c.status === 'in_progress') || MOCK_CASES[1];
  const resolvedCount = MOCK_CASES.filter(c => c.status === 'resolved').length;
  const totalCount = MOCK_CASES.length;

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Header with logo & branding */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.logoRow} onPress={() => router.push('/(app)/(tabs)/profile')} activeOpacity={0.8}>
            <Image source={require('../../../assets/logo.jpg')} style={styles.logoImg} />
            <View>
              <Text style={styles.brandName}>CivicConnect</Text>
              <Text style={styles.brandSub}>Citizen App</Text>
            </View>
          </TouchableOpacity>
          <TouchableOpacity style={styles.notifBtn} onPress={() => router.push('/(app)/(tabs)/notifications')}>
            <Text style={styles.notifIcon}>🔔</Text>
            <View style={styles.notifBadge} />
          </TouchableOpacity>
        </View>

        {/* Greeting */}
        <View style={styles.greetingSection}>
          <Text style={styles.greetingText}>Hi, {MOCK_USER.name} 👋</Text>
          <Text style={styles.wardText}>{MOCK_USER.ward} • {MOCK_USER.locality}</Text>
        </View>

        {/* Title */}
        <View style={styles.titleSection}>
          <Text style={styles.mainTitle}>WHAT NEEDS</Text>
          <View style={styles.youBadgeContainer}>
            <View style={styles.youBadgeShadow} />
            <View style={styles.youBadge}>
              <Text style={styles.youText}>YOU</Text>
            </View>
          </View>
        </View>

        {/* Hero Verification Card */}
        <TouchableOpacity 
          style={styles.heroCardContainer}
          onPress={() => router.push(`/(app)/case/${verificationCase.id}`)}
          activeOpacity={0.9}
        >
          <View style={styles.heroCardShadow} />
          <View style={styles.heroCard}>
            <View style={styles.heroCardTop}>
              <View style={styles.pillVerify}>
                <Text style={styles.pillVerifyText}>✓ Verify</Text>
              </View>
              <Text style={styles.caseId}>{verificationCase.case_number}</Text>
            </View>
            <Text style={styles.heroTitle}>{verificationCase.title}</Text>
            <Text style={styles.heroDesc}>The team says the work is done. Only you can confirm it.</Text>
            
            <View style={styles.confirmBtn}>
              <Text style={styles.confirmBtnText}>Confirm the fix</Text>
              <View style={styles.confirmArrowBtn}>
                <Text style={styles.confirmArrow}>→</Text>
              </View>
            </View>
          </View>
        </TouchableOpacity>

        {/* In Progress Card */}
        <TouchableOpacity 
          style={styles.cardContainer}
          onPress={() => router.push(`/(app)/case/${inProgressCase.id}`)}
          activeOpacity={0.9}
        >
          <View style={styles.cardShadow} />
          <View style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.pillInProgress}>
                <Text style={styles.pillInProgressText}>In progress</Text>
              </View>
              <Text style={styles.caseId}>{inProgressCase.case_number}</Text>
            </View>
            <Text style={styles.cardTitle}>{inProgressCase.title}</Text>
            <Text style={styles.cardDesc}>{inProgressCase.supporter_count} neighbours back this report. A team is working on it.</Text>
          </View>
        </TouchableOpacity>

        {/* Quick Stats */}
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <View style={styles.statShadow} />
            <View style={styles.statInner}>
              <Text style={styles.statNumber}>{totalCount}</Text>
              <Text style={styles.statLabel}>Reported</Text>
            </View>
          </View>
          <View style={styles.statItem}>
            <View style={styles.statShadow} />
            <View style={[styles.statInner, { backgroundColor: Colors.lime }]}>
              <Text style={styles.statNumber}>{resolvedCount}</Text>
              <Text style={styles.statLabel}>Resolved</Text>
            </View>
          </View>
          <View style={styles.statItem}>
            <View style={styles.statShadow} />
            <View style={[styles.statInner, { backgroundColor: Colors.amber }]}>
              <Text style={styles.statNumber}>{totalCount - resolvedCount}</Text>
              <Text style={styles.statLabel}>Active</Text>
            </View>
          </View>
        </View>

        {/* Action Grid */}
        <Text style={styles.sectionLabel}>QUICK ACTIONS</Text>
        <View style={styles.actionGrid}>
          <View style={styles.gridItem}>
            <View style={styles.gridShadow} />
            <TouchableOpacity 
              style={[styles.gridInner, { backgroundColor: Colors.lime }]}
              onPress={() => router.push('/(app)/report')}
              activeOpacity={0.8}
            >
              <Text style={styles.gridIcon}>📷</Text>
              <Text style={styles.gridTitle}>Report Issue</Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.gridItem}>
            <View style={styles.gridShadow} />
            <TouchableOpacity 
              style={styles.gridInner}
              onPress={() => router.push('/(app)/(tabs)/map')}
              activeOpacity={0.8}
            >
              <Text style={styles.gridIcon}>🗺️</Text>
              <Text style={styles.gridTitle}>City Map</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.gridItem}>
            <View style={styles.gridShadow} />
            <TouchableOpacity 
              style={styles.gridInner}
              onPress={() => router.push('/(app)/(tabs)/my-cases')}
              activeOpacity={0.8}
            >
              <Text style={styles.gridIcon}>📋</Text>
              <Text style={styles.gridTitle}>My Cases</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.gridItem}>
            <View style={styles.gridShadow} />
            <TouchableOpacity 
              style={styles.gridInner}
              onPress={() => router.push('/(app)/(tabs)/community')}
              activeOpacity={0.8}
            >
              <Text style={styles.gridIcon}>🤝</Text>
              <Text style={styles.gridTitle}>Community</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.ground },
  container: { flex: 1 },
  scrollContent: { paddingBottom: Layout.bottomNavHeight + Spacing[10] },

  // Header
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingTop: Spacing[3], paddingBottom: Spacing[2] },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing[3] },
  logoImg: { width: 42, height: 42, borderRadius: 12, borderWidth: 2, borderColor: Colors.ink },
  brandName: { fontSize: 18, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -0.5 },
  brandSub: { fontSize: 11, color: Colors.muted, fontWeight: Typography.bold },
  notifBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  notifIcon: { fontSize: 18 },
  notifBadge: { position: 'absolute', top: 6, right: 6, width: 10, height: 10, borderRadius: 5, backgroundColor: Colors.fire, borderWidth: 1.5, borderColor: Colors.surface },

  // Greeting
  greetingSection: { paddingHorizontal: Spacing[4], paddingTop: Spacing[3], marginBottom: Spacing[2] },
  greetingText: { fontSize: 22, fontWeight: Typography.bold, color: Colors.ink },
  wardText: { fontSize: 13, color: Colors.muted, marginTop: 2 },

  // Title
  titleSection: { paddingHorizontal: Spacing[4], marginBottom: Spacing[5] },
  mainTitle: { fontSize: 40, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1, lineHeight: 42 },
  youBadgeContainer: { marginTop: Spacing[1], alignSelf: 'flex-start' },
  youBadgeShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.sm },
  youBadge: { backgroundColor: Colors.ink, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.sm, borderWidth: 2, borderColor: Colors.surface },
  youText: { color: Colors.lime, fontSize: 26, fontWeight: Typography.black, letterSpacing: -0.5 },

  // Hero Card
  heroCardContainer: { marginHorizontal: Spacing[4], marginBottom: Spacing[4] },
  heroCardShadow: { position: 'absolute', top: 5, left: 5, right: -5, bottom: -5, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  heroCard: { backgroundColor: Colors.lime, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4] },
  heroCardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing[3] },
  pillVerify: { backgroundColor: Colors.ink, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  pillVerifyText: { color: Colors.lime, fontSize: 12, fontWeight: Typography.bold },
  caseId: { fontFamily: 'monospace', fontSize: 12, color: Colors.ink, fontWeight: Typography.bold },
  heroTitle: { fontSize: 20, fontWeight: Typography.bold, color: Colors.ink, marginBottom: Spacing[2], lineHeight: 26 },
  heroDesc: { fontSize: 14, color: Colors.ink, marginBottom: Spacing[4], lineHeight: 20 },
  confirmBtn: { backgroundColor: Colors.ink, borderRadius: Radii.lg, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing[3], paddingHorizontal: Spacing[4] },
  confirmBtnText: { color: Colors.surface, fontSize: 16, fontWeight: Typography.bold },
  confirmArrowBtn: { width: 30, height: 30, borderRadius: 15, backgroundColor: Colors.fire, alignItems: 'center', justifyContent: 'center' },
  confirmArrow: { color: Colors.surface, fontWeight: Typography.bold, fontSize: 16 },

  // Regular card
  cardContainer: { marginHorizontal: Spacing[4], marginBottom: Spacing[5] },
  cardShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  card: { backgroundColor: Colors.surface, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4] },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing[3] },
  pillInProgress: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full },
  pillInProgressText: { color: Colors.ink, fontSize: 12, fontWeight: Typography.bold },
  cardTitle: { fontSize: 17, fontWeight: Typography.bold, color: Colors.ink, marginBottom: Spacing[1], lineHeight: 22 },
  cardDesc: { fontSize: 13, color: Colors.muted, lineHeight: 18 },

  // Stats row
  statsRow: { flexDirection: 'row', paddingHorizontal: Spacing[4], gap: Spacing[3], marginBottom: Spacing[5] },
  statItem: { flex: 1 },
  statShadow: { position: 'absolute', top: 3, left: 3, right: -3, bottom: -3, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  statInner: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[3], alignItems: 'center' },
  statNumber: { fontSize: 28, fontWeight: Typography.black, color: Colors.ink },
  statLabel: { fontSize: 11, fontWeight: Typography.bold, color: Colors.ink, marginTop: 2 },

  // Section
  sectionLabel: { fontFamily: 'monospace', fontSize: 12, fontWeight: Typography.bold, color: Colors.muted, paddingHorizontal: Spacing[4], marginBottom: Spacing[3], letterSpacing: 1 },

  // Action Grid
  actionGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: Spacing[4], justifyContent: 'space-between' },
  gridItem: { width: '48%', height: 100, marginBottom: Spacing[3] },
  gridShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  gridInner: { flex: 1, backgroundColor: Colors.surface, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[3], justifyContent: 'space-between' },
  gridIcon: { fontSize: 24 },
  gridTitle: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
});
