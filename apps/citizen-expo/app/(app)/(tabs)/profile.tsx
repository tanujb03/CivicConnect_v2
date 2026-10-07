import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';
import { useAuthContext } from '../../../src/context/AuthContext';
import { MOCK_USER, MOCK_CASES } from '../../../src/data/mockData';

function SettingRow({ label, subLabel, value, onPress, isSwitch = false, isLast = false, navTarget }: { label: string; subLabel?: string; value?: boolean; onPress?: () => void; isSwitch?: boolean; isLast?: boolean; navTarget?: string; }) {
  const router = useRouter();
  return (
    <TouchableOpacity 
      style={[styles.settingRow, !isLast && styles.settingRowBorder]} 
      onPress={() => {
        if (navTarget) router.push(navTarget as any);
        else if (onPress) onPress();
      }}
      disabled={!onPress && !isSwitch && !navTarget}
      activeOpacity={0.7}
    >
      <View style={{ flex: 1 }}>
        <Text style={styles.settingLabel}>{label}</Text>
        {subLabel && <Text style={styles.settingSub}>{subLabel}</Text>}
      </View>
      {isSwitch ? (
        <Switch
          value={value}
          onValueChange={onPress}
          trackColor={{ false: Colors.dot, true: Colors.lime }}
          thumbColor={Colors.ink}
        />
      ) : (
        <Text style={styles.settingArrow}>›</Text>
      )}
    </TouchableOpacity>
  );
}

export default function ProfileScreen() {
  const router = useRouter();
  const { logout } = useAuthContext();
  const [notifsEnabled, setNotifsEnabled] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  const reportedCount = MOCK_CASES.length;
  const resolvedCount = MOCK_CASES.filter(c => c.status === 'resolved').length;

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backBtnText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Profile</Text>
          <View style={{ width: 44 }} />
        </View>

        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          {/* Identity Card */}
          <View style={styles.identityContainer}>
            <View style={styles.identityShadow} />
            <View style={styles.identityCard}>
              <Image source={require('../../../assets/logo.jpg')} style={styles.avatarImg} />
              <View style={{ flex: 1 }}>
                <Text style={styles.identityName}>{MOCK_USER.name}</Text>
                <Text style={styles.identityEmail}>{MOCK_USER.email}</Text>
                <View style={styles.roleBadge}>
                  <Text style={styles.roleText}>Citizen • CivicConnect</Text>
                </View>
              </View>
            </View>
          </View>

          {/* Stats */}
          <View style={styles.statsGrid}>
            <View style={styles.statBoxContainer}>
              <View style={styles.statShadow} />
              <View style={styles.statBox}>
                <Text style={styles.statLabel}>REPORTED</Text>
                <Text style={styles.statValue}>{reportedCount}</Text>
              </View>
            </View>
            <View style={styles.statBoxContainer}>
              <View style={styles.statShadow} />
              <View style={[styles.statBox, { backgroundColor: Colors.lime }]}>
                <Text style={styles.statLabel}>RESOLVED</Text>
                <Text style={styles.statValue}>{resolvedCount}</Text>
              </View>
            </View>
          </View>

          {/* Settings */}
          <View style={styles.settingsContainer}>
            <View style={styles.settingsShadow} />
            <View style={styles.settingsCard}>
              <SettingRow label="Notifications" subLabel="Case updates & reminders" isSwitch value={notifsEnabled} onPress={() => setNotifsEnabled(!notifsEnabled)} />
              <SettingRow label="Language" subLabel="English" navTarget="/(app)/settings/language" />
              <SettingRow label="Accessibility" subLabel="Text size, contrast" navTarget="/(app)/settings/accessibility" />
              <SettingRow label="Dark mode" isSwitch value={darkMode} onPress={() => setDarkMode(!darkMode)} />
              <SettingRow label="Location" subLabel={MOCK_USER.locality} />
              <SettingRow label="Privacy" subLabel="Your name is never shown publicly" isLast />
            </View>
          </View>

          {/* Logout */}
          <TouchableOpacity 
            style={styles.logoutBtn}
            onPress={() => {
              logout();
              router.replace('/(auth)/welcome');
            }}
          >
            <Text style={styles.logoutText}>Log out</Text>
          </TouchableOpacity>

          <Text style={styles.footerNote}>
            CivicConnect Citizen App v2.0{'\n'}Built for Ranchi Municipal Corporation
          </Text>
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.ground },
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4] },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink },
  scrollContent: { paddingHorizontal: Spacing[4], paddingBottom: Layout.bottomNavHeight + Spacing[6] },
  identityContainer: { marginBottom: Spacing[4] },
  identityShadow: { position: 'absolute', top: 5, left: 5, right: -5, bottom: -5, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  identityCard: { backgroundColor: Colors.wine, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4], flexDirection: 'row', alignItems: 'center', gap: Spacing[4] },
  avatarImg: { width: 56, height: 56, borderRadius: 16, borderWidth: 2, borderColor: Colors.surface },
  identityName: { fontSize: 18, fontWeight: Typography.bold, color: Colors.surface, marginBottom: 2 },
  identityEmail: { fontSize: 12, color: Colors.surface, opacity: 0.8, marginBottom: Spacing[2] },
  roleBadge: { backgroundColor: Colors.lime, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full, alignSelf: 'flex-start', borderWidth: 1.5, borderColor: Colors.ink },
  roleText: { fontSize: 11, fontWeight: Typography.bold, color: Colors.ink },
  statsGrid: { flexDirection: 'row', gap: Spacing[3], marginBottom: Spacing[4] },
  statBoxContainer: { flex: 1 },
  statShadow: { position: 'absolute', top: 3, left: 3, right: -3, bottom: -3, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  statBox: { backgroundColor: Colors.surface, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[3] },
  statLabel: { fontFamily: 'monospace', fontSize: 10, fontWeight: Typography.bold, color: Colors.ink, marginBottom: 4 },
  statValue: { fontSize: 32, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1 },
  settingsContainer: { marginBottom: Spacing[4] },
  settingsShadow: { position: 'absolute', top: 5, left: 5, right: -5, bottom: -5, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  settingsCard: { backgroundColor: Colors.surface, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4] },
  settingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing[3] },
  settingRowBorder: { borderBottomWidth: 1.5, borderBottomColor: Colors.dot },
  settingLabel: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  settingSub: { fontSize: 12, color: Colors.muted, marginTop: 2 },
  settingArrow: { fontSize: 24, color: Colors.muted },
  logoutBtn: { borderWidth: 2, borderColor: Colors.fire, borderRadius: Radii.lg, paddingVertical: Spacing[3], alignItems: 'center', marginBottom: Spacing[4] },
  logoutText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.fire },
  footerNote: { fontSize: 12, color: Colors.muted, textAlign: 'center', lineHeight: 18 },
});
