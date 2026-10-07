import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Radii, Shadows, Spacing } from '../../src/theme/tokens';
import { FontFamily } from '../../src/theme/fonts';
import { Card, KpiCard, HardShadow, StateView, useToast } from '../../src/ui';
import { apiClient } from '../../src/api/client';

function ProfileRow({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <View style={styles.profileRow}>
      <View style={styles.profileRowIcon}>
        <Ionicons name={icon as any} size={18} color={Colors.wine} />
      </View>
      <View style={styles.profileRowContent}>
        <Text style={styles.profileRowLabel}>{label}</Text>
        <Text style={styles.profileRowValue}>{value}</Text>
      </View>
    </View>
  );
}

export default function ProfileScreen() {
  const { show } = useToast();

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => apiClient.getProfile(),
  });

  const { data: kpi } = useQuery({
    queryKey: ['kpi'],
    queryFn: () => apiClient.getKpi(),
  });

  const handleLogout = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: () => {
            show('Signed out successfully', 'info');
            router.replace('/sign-in');
          },
        },
      ]
    );
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="loading" title="Loading profile..." />
      </SafeAreaView>
    );
  }

  if (!profile) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="error" title="Profile not found" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.eyebrow}>MY ACCOUNT</Text>
          <Text style={styles.heading}>ME</Text>
        </View>

        {/* Avatar card */}
        <HardShadow offset={Shadows.card} radius={Radii.xl} containerStyle={styles.avatarCardWrapper}>
          <View style={styles.avatarCard}>
            <View style={styles.avatarCircle}>
              <Text style={styles.avatarInitials}>
                {profile.name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
              </Text>
            </View>
            <View style={styles.avatarInfo}>
              <Text style={styles.avatarName}>{profile.name}</Text>
              <Text style={styles.avatarId}>{profile.employeeId}</Text>
              <View style={styles.avatarBadge}>
                <Ionicons name="shield-checkmark" size={12} color={Colors.wine} />
                <Text style={styles.avatarBadgeText}>{profile.department}</Text>
              </View>
            </View>
          </View>
        </HardShadow>

        {/* KPI summary */}
        {kpi ? (
          <>
            <Text style={styles.sectionLabel}>TODAY'S STATS</Text>
            <View style={styles.kpiRow}>
              <KpiCard
                value={kpi.openCount}
                label="Open"
                backgroundColor={Colors.wine}
                textColor={Colors.lime}
              />
              <View style={{ width: 8 }} />
              <KpiCard
                value={kpi.doneToday}
                label="Done"
                backgroundColor={Colors.limeTint}
                textColor={Colors.ink}
              />
              <View style={{ width: 8 }} />
              <KpiCard
                value={`${Math.round(kpi.slaBreachRate * 100)}%`}
                label="SLA"
                backgroundColor={kpi.slaBreachRate > 0.2 ? Colors.fire : Colors.surface}
                textColor={kpi.slaBreachRate > 0.2 ? Colors.onFire : Colors.ink}
              />
            </View>
          </>
        ) : null}

        {/* Details */}
        <Text style={styles.sectionLabel}>CONTACT & ASSIGNMENT</Text>
        <Card shadow="hard" containerStyle={styles.detailCard}>
          <ProfileRow icon="call-outline" label="Phone" value={profile.phone} />
          <View style={styles.rowDivider} />
          <ProfileRow icon="mail-outline" label="Email" value={profile.email} />
          <View style={styles.rowDivider} />
          <ProfileRow icon="map-outline" label="Ward" value={profile.ward} />
          <View style={styles.rowDivider} />
          <ProfileRow icon="business-outline" label="Department" value={profile.department} />
        </Card>

        {/* Developer Primitives Showcase */}
        <Text style={styles.sectionLabel}>DEVELOPER TOOLS</Text>
        <Card
          shadow="hard"
          containerStyle={styles.detailCard}
          onPress={() => router.push('/dev/primitives' as any)}
          accessibilityLabel="Open UI Primitives Showcase"
        >
          <View style={styles.profileRow}>
            <View style={styles.profileRowIcon}>
              <Ionicons name="cube-outline" size={18} color={Colors.wine} />
            </View>
            <View style={styles.profileRowContent}>
              <Text style={styles.profileRowLabel}>Design System</Text>
              <Text style={styles.profileRowValue}>UI Primitives Showcase</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={Colors.muted} />
          </View>
        </Card>

        {/* Logout */}
        <HardShadow offset={Shadows.hard} radius={Radii.md} containerStyle={styles.logoutWrapper}>
          <Pressable
            style={styles.logoutButton}
            onPress={handleLogout}
            accessibilityLabel="Sign out"
            accessibilityRole="button"
          >
            <Ionicons name="log-out-outline" size={20} color={Colors.onFire} />
            <Text style={styles.logoutText}>SIGN OUT</Text>
          </Pressable>
        </HardShadow>

        <Text style={styles.appVersion}>CivicConnect Field Worker v1.0.0-beta</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.ground },
  content: {
    paddingHorizontal: Spacing.screenH,
    paddingBottom: 48,
  },
  header: { paddingTop: 20, paddingBottom: 20 },
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
  avatarCardWrapper: { width: '100%', marginBottom: 24 },
  avatarCard: {
    backgroundColor: Colors.wine,
    borderRadius: Radii.xl,
    borderWidth: 2,
    borderColor: Colors.ink,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  avatarCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.lime,
    borderWidth: 2,
    borderColor: Colors.ink,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarInitials: {
    fontFamily: FontFamily.display,
    fontSize: 22,
    color: Colors.ink,
  },
  avatarInfo: { flex: 1 },
  avatarName: {
    fontFamily: FontFamily.display,
    fontSize: 18,
    color: Colors.onWine,
    marginBottom: 2,
  },
  avatarId: {
    fontFamily: FontFamily.mono,
    fontSize: 12,
    color: Colors.dot,
    marginBottom: 8,
    letterSpacing: 1,
  },
  avatarBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.lime,
    borderRadius: Radii.full,
    alignSelf: 'flex-start',
    paddingVertical: 3,
    paddingHorizontal: 10,
    borderWidth: 1.5,
    borderColor: Colors.ink,
  },
  avatarBadgeText: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.ink,
    letterSpacing: 0.5,
  },
  sectionLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1.5,
    marginBottom: 10,
    textTransform: 'uppercase',
  },
  kpiRow: { flexDirection: 'row', marginBottom: 24 },
  detailCard: { width: '100%', marginBottom: 24 },
  profileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    gap: 12,
  },
  profileRowIcon: {
    width: 36,
    height: 36,
    borderRadius: Radii.md,
    backgroundColor: Colors.ground,
    justifyContent: 'center',
    alignItems: 'center',
  },
  profileRowContent: { flex: 1 },
  profileRowLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  profileRowValue: {
    fontFamily: FontFamily.sans,
    fontSize: FontSizes.body,
    color: Colors.ink,
  },
  rowDivider: { height: 1, backgroundColor: Colors.dot },
  logoutWrapper: { width: '100%', marginBottom: 24 },
  logoutButton: {
    backgroundColor: Colors.fire,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  logoutText: {
    fontFamily: FontFamily.display,
    fontSize: 16,
    color: Colors.onFire,
    letterSpacing: 1,
  },
  appVersion: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    color: Colors.muted,
    textAlign: 'center',
    letterSpacing: 0.5,
  },
});
