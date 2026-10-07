import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../../src/constants/theme';
import { useAuthContext } from '../../../src/context/AuthContext';

function SettingRow({ label, subLabel, value, onPress, isSwitch = false, isLast = false }: { label: string; subLabel?: string; value?: boolean; onPress?: () => void; isSwitch?: boolean; isLast?: boolean; }) {
  return (
    <TouchableOpacity 
      style={[styles.settingRow, !isLast && styles.settingRowBorder]} 
      onPress={onPress}
      disabled={!onPress && !isSwitch}
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
          trackColor={{ false: Colors.surface, true: Colors.lime }}
          thumbColor={Colors.ink}
          ios_backgroundColor={Colors.surface}
          style={styles.switch}
        />
      ) : (
        <Text style={styles.settingArrow}>›</Text>
      )}
    </TouchableOpacity>
  );
}

export default function ProfileScreen() {
  const router = useRouter();
  const { user } = useAuthContext();
  const [notifsEnabled, setNotifsEnabled] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backBtnText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle} numberOfLines={1}>C13 • PROFILE</Text>
          <View style={{ width: 44 }} />
        </View>

        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <View style={styles.identityContainer}>
            <View style={styles.identityShadow} />
            <View style={styles.identityCard}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>C3</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.identityName}>Synthetic Citizen 003</Text>
                <Text style={styles.identityEmail}>citizen003@demo.civicconnect.test</Text>
                <View style={styles.roleBadge}>
                  <Text style={styles.roleText}>Citizen</Text>
                </View>
              </View>
            </View>
          </View>

          <View style={styles.statsGrid}>
            <View style={styles.statBoxContainer}>
              <View style={styles.statShadow} />
              <View style={styles.statBox}>
                <Text style={styles.statLabel}>CASES REPORTED</Text>
                <Text style={styles.statValue}>12</Text>
              </View>
            </View>
            <View style={styles.statBoxContainer}>
              <View style={styles.statShadow} />
              <View style={[styles.statBox, { backgroundColor: Colors.lime }]}>
                <Text style={styles.statLabel}>RESOLVED</Text>
                <Text style={styles.statValue}>7</Text>
              </View>
            </View>
          </View>

          <View style={styles.statsGrid}>
            <View style={[styles.statBoxContainer, { opacity: 0.7 }]}>
              <View style={[styles.statBox, styles.statBoxDashed]}>
                <Text style={styles.statLabel}>CASES BACKED</Text>
                <Text style={styles.statValue}>N/A</Text>
                <Text style={styles.statSub}>needs backend</Text>
              </View>
            </View>
            <View style={[styles.statBoxContainer, { opacity: 0.7 }]}>
              <View style={[styles.statBox, styles.statBoxDashed]}>
                <Text style={styles.statLabel}>FIXES CONFIRMED</Text>
                <Text style={styles.statValue}>N/A</Text>
                <Text style={styles.statSub}>needs backend</Text>
              </View>
            </View>
          </View>

          <View style={styles.settingsContainer}>
            <View style={styles.settingsShadow} />
            <View style={styles.settingsCard}>
              <SettingRow label="Notifications" subLabel="Case updates" isSwitch value={notifsEnabled} onPress={() => setNotifsEnabled(!notifsEnabled)} />
              <SettingRow label="Language" subLabel="हिन्दी" />
              <SettingRow label="Accessibility" subLabel="Text size, contrast, motion" />
              <SettingRow label="Dark mode" isSwitch value={darkMode} onPress={() => setDarkMode(!darkMode)} />
              <SettingRow label="Location" subLabel="While using the app" />
              <SettingRow label="Privacy" subLabel="Your name is never shown to other citizens" isLast />
            </View>
          </View>

          <Text style={styles.footerNote}>
            There is no public score and no ranking. Counts come from your own cases (GET /cases). Backed cases and confirmed fixes need a profile endpoint.
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
  headerTitle: { fontFamily: 'monospace', fontSize: 14, fontWeight: Typography.bold, color: Colors.muted },
  scrollContent: { paddingHorizontal: Spacing[4], paddingBottom: Spacing[10] },
  identityContainer: { marginBottom: Spacing[4] },
  identityShadow: { position: 'absolute', top: 6, left: 6, right: -6, bottom: -6, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  identityCard: { backgroundColor: Colors.wine, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4], flexDirection: 'row', alignItems: 'center', gap: Spacing[4] },
  avatar: { width: 64, height: 64, borderRadius: 32, backgroundColor: Colors.lime, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 24, fontWeight: Typography.black, color: Colors.ink },
  identityName: { fontSize: 18, fontWeight: Typography.bold, color: Colors.surface, marginBottom: 2 },
  identityEmail: { fontSize: 12, color: Colors.surface, opacity: 0.8, marginBottom: Spacing[2] },
  roleBadge: { backgroundColor: Colors.lime, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1], borderRadius: Radii.full, alignSelf: 'flex-start', borderWidth: 1.5, borderColor: Colors.ink },
  roleText: { fontSize: 12, fontWeight: Typography.bold, color: Colors.ink },
  statsGrid: { flexDirection: 'row', gap: Spacing[3], marginBottom: Spacing[3] },
  statBoxContainer: { flex: 1 },
  statShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  statBox: { backgroundColor: Colors.surface, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[3] },
  statBoxDashed: { borderStyle: 'dashed', borderWidth: 2 },
  statLabel: { fontFamily: 'monospace', fontSize: 10, fontWeight: Typography.bold, color: Colors.ink, marginBottom: 4 },
  statValue: { fontSize: 36, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1 },
  statSub: { fontSize: 10, color: Colors.muted },
  settingsContainer: { marginTop: Spacing[2], marginBottom: Spacing[4] },
  settingsShadow: { position: 'absolute', top: 6, left: 6, right: -6, bottom: -6, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  settingsCard: { backgroundColor: Colors.surface, borderWidth: 3, borderColor: Colors.ink, borderRadius: Radii.xl, padding: Spacing[4] },
  settingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing[3] },
  settingRowBorder: { borderBottomWidth: 1.5, borderBottomColor: Colors.ink, borderStyle: 'dashed' },
  settingLabel: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  settingSub: { fontSize: 12, color: Colors.muted, marginTop: 2 },
  settingArrow: { fontSize: 24, color: Colors.ink },
  switch: { transform: [{ scaleX: 1.1 }, { scaleY: 1.1 }], borderWidth: 2, borderColor: Colors.ink, borderRadius: 16 },
  footerNote: { fontSize: 12, color: Colors.muted, textAlign: 'center', lineHeight: 18, paddingHorizontal: Spacing[4] },
});
