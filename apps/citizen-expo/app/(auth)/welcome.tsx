/**
 * C01 — Welcome
 * Direction A aesthetic: ink borders, hard shadows, lime/wine/fire palette.
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Modal, FlatList, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../src/constants/theme';
import { useAppSettings } from '../../src/context/AppSettingsContext';
import { StatusBar } from 'expo-status-bar';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
  { code: 'ta', label: 'தமிழ்' },
  { code: 'te', label: 'తెలుగు' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
  { code: 'bn', label: 'বাংলা' },
  { code: 'gu', label: 'ગુજરાતી' },
];

const WORKFLOW_STEPS = [
  { icon: '📸', label: 'Spot the issue' },
  { icon: '📍', label: 'Report with location' },
  { icon: '🤖', label: 'AI classifies it' },
  { icon: '🏛️', label: 'City acts on it' },
  { icon: '✅', label: 'You verify resolution' },
];

export default function WelcomeScreen() {
  const router = useRouter();
  const { settings, setLanguage } = useAppSettings();
  const [showLangModal, setShowLangModal] = useState(false);
  const currentLang = LANGUAGES.find(l => l.code === settings.language) ?? LANGUAGES[0];

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <StatusBar style="dark" />

      <View style={styles.topBar}>
        <View style={styles.logoRow}>
          <Image source={require('../../assets/logo.jpg')} style={styles.logoImg} />
          <View>
            <Text style={styles.appName}>CivicConnect</Text>
            <Text style={styles.appVersion}>Citizen App</Text>
          </View>
        </View>
        <TouchableOpacity onPress={() => setShowLangModal(true)} style={styles.langButton}>
          <Text style={styles.langButtonText}>🌐 {currentLang.label}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.missionSection}>
          <Text style={styles.missionHeadline}>YOUR CITY,{'\n'}YOUR VOICE,</Text>
          <View style={styles.changeBadgeContainer}>
            <View style={styles.changeBadgeShadow} />
            <View style={styles.changeBadge}>
              <Text style={styles.changeText}>YOUR CHANGE.</Text>
            </View>
          </View>
          <Text style={styles.missionSub}>
            Report civic issues. Track their resolution. Build a better city — together.
          </Text>
        </View>

        <View style={styles.workflowContainer}>
          <View style={styles.workflowShadow} />
          <View style={styles.workflowCard}>
            <Text style={styles.workflowTitle}>HOW IT WORKS</Text>
            {WORKFLOW_STEPS.map((step, index) => (
              <View key={index} style={styles.workflowRow}>
                <View style={styles.stepIconBox}>
                  <Text style={styles.stepEmoji}>{step.icon}</Text>
                </View>
                <Text style={styles.stepLabel}>{step.label}</Text>
                {index < WORKFLOW_STEPS.length - 1 && <View style={styles.stepConnector} />}
              </View>
            ))}
          </View>
        </View>

        <View style={styles.trustRow}>
          <View style={styles.trustItem}>
            <Text style={styles.trustIcon}>🤖</Text>
            <Text style={styles.trustLabel}>AI triage</Text>
          </View>
          <View style={styles.trustDivider} />
          <View style={styles.trustItem}>
            <Text style={styles.trustIcon}>📶</Text>
            <Text style={styles.trustLabel}>Works offline</Text>
          </View>
          <View style={styles.trustDivider} />
          <View style={styles.trustItem}>
            <Text style={styles.trustIcon}>🔒</Text>
            <Text style={styles.trustLabel}>Secure</Text>
          </View>
        </View>
      </ScrollView>

      <View style={styles.ctaSection}>
        <View style={styles.primaryCtaContainer}>
          <View style={styles.primaryCtaShadow} />
          <TouchableOpacity style={styles.primaryCta} onPress={() => router.push('/(auth)/onboarding')}>
            <Text style={styles.primaryCtaText}>Get Started</Text>
            <View style={styles.ctaArrow}>
              <Text style={styles.ctaArrowText}>→</Text>
            </View>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.secondaryCta} onPress={() => router.push('/(auth)/login')}>
          <Text style={styles.secondaryCtaText}>I already have an account</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.a11yButton} onPress={() => router.push('/(app)/settings/accessibility')}>
          <Text style={styles.a11yText}>♿ Accessibility</Text>
        </TouchableOpacity>
      </View>

      <Modal visible={showLangModal} transparent animationType="slide" onRequestClose={() => setShowLangModal(false)}>
        <TouchableOpacity style={styles.modalOverlay} activeOpacity={1} onPress={() => setShowLangModal(false)}>
          <View style={styles.langModal}>
            <View style={styles.langModalHandle} />
            <Text style={styles.langModalTitle}>Select Language</Text>
            <FlatList
              data={LANGUAGES}
              keyExtractor={item => item.code}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.langOption, item.code === settings.language && styles.langOptionActive]}
                  onPress={async () => { await setLanguage(item.code); setShowLangModal(false); }}
                >
                  <Text style={[styles.langOptionText, item.code === settings.language && styles.langOptionTextActive]}>
                    {item.label}
                  </Text>
                  {item.code === settings.language && <Text style={styles.checkmark}>✓</Text>}
                </TouchableOpacity>
              )}
            />
          </View>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.wine },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingTop: Spacing[4], paddingBottom: Spacing[3] },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing[3] },
  logoImg: { width: 44, height: 44, borderRadius: 12, borderWidth: 2, borderColor: Colors.surface },
  appName: { color: Colors.surface, fontSize: 18, fontWeight: Typography.black, letterSpacing: -0.5 },
  appVersion: { color: 'rgba(255,255,255,0.7)', fontSize: 11, fontWeight: Typography.bold },
  langButton: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[1.5], backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: Radii.full, borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.2)' },
  langButtonText: { color: Colors.surface, fontSize: 13, fontWeight: Typography.medium },
  scrollContent: { paddingHorizontal: Spacing[4], paddingBottom: Spacing[4] },
  missionSection: { marginTop: Spacing[6], marginBottom: Spacing[6] },
  missionHeadline: { color: Colors.surface, fontSize: 36, fontWeight: Typography.black, lineHeight: 40, letterSpacing: -1 },
  changeBadgeContainer: { alignSelf: 'flex-start', marginTop: Spacing[1], marginBottom: Spacing[4] },
  changeBadgeShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.surface, borderRadius: Radii.sm },
  changeBadge: { backgroundColor: Colors.lime, paddingHorizontal: Spacing[3], paddingVertical: 2, borderRadius: Radii.sm, borderWidth: 2, borderColor: Colors.ink },
  changeText: { color: Colors.ink, fontSize: 28, fontWeight: Typography.black, letterSpacing: -0.5 },
  missionSub: { color: 'rgba(255,255,255,0.7)', fontSize: 15, lineHeight: 22 },
  workflowContainer: { marginBottom: Spacing[5] },
  workflowShadow: { position: 'absolute', top: 6, left: 6, right: -6, bottom: -6, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  workflowCard: { backgroundColor: Colors.surface, borderRadius: Radii.xl, padding: Spacing[5], borderWidth: 3, borderColor: Colors.ink },
  workflowTitle: { fontFamily: 'monospace', color: Colors.muted, fontSize: 12, fontWeight: Typography.bold, letterSpacing: 1, marginBottom: Spacing[4] },
  workflowRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing[3], marginBottom: Spacing[1], position: 'relative' },
  stepIconBox: { width: 40, height: 40, borderRadius: Radii.md, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.ground, borderWidth: 1.5, borderColor: Colors.ink },
  stepEmoji: { fontSize: 20 },
  stepLabel: { color: Colors.ink, fontSize: 15, fontWeight: Typography.bold, flex: 1 },
  stepConnector: { position: 'absolute', left: 19, bottom: -8, width: 2, height: 16, backgroundColor: Colors.dot },
  trustRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: Radii.lg, paddingVertical: Spacing[4], paddingHorizontal: Spacing[3], borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.15)' },
  trustItem: { alignItems: 'center', flex: 1 },
  trustIcon: { fontSize: 18, marginBottom: 2 },
  trustLabel: { color: 'rgba(255,255,255,0.6)', fontSize: 12, fontWeight: Typography.bold, textAlign: 'center' },
  trustDivider: { width: 1, height: 32, backgroundColor: 'rgba(255,255,255,0.15)' },
  ctaSection: { paddingHorizontal: Spacing[4], paddingBottom: Spacing[6], gap: Spacing[3] },
  primaryCtaContainer: { width: '100%' },
  primaryCtaShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  primaryCta: { backgroundColor: Colors.lime, borderRadius: Radii.lg, paddingVertical: Spacing[4], paddingHorizontal: Spacing[4], flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 2, borderColor: Colors.ink },
  primaryCtaText: { color: Colors.ink, fontSize: 18, fontWeight: Typography.bold },
  ctaArrow: { width: 32, height: 32, borderRadius: 16, backgroundColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  ctaArrowText: { color: Colors.lime, fontWeight: Typography.bold, fontSize: 16 },
  secondaryCta: { borderRadius: Radii.lg, paddingVertical: Spacing[4], alignItems: 'center', borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)' },
  secondaryCtaText: { color: Colors.surface, fontSize: 15, fontWeight: Typography.bold },
  a11yButton: { alignItems: 'center', paddingVertical: Spacing[2] },
  a11yText: { color: 'rgba(255,255,255,0.45)', fontSize: 13, fontWeight: Typography.medium },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  langModal: { backgroundColor: Colors.surface, borderTopLeftRadius: Radii['2xl'], borderTopRightRadius: Radii['2xl'], paddingTop: Spacing[3], paddingBottom: Spacing[10], maxHeight: '70%', borderWidth: 3, borderBottomWidth: 0, borderColor: Colors.ink },
  langModalHandle: { width: 36, height: 5, backgroundColor: Colors.dot, borderRadius: Radii.full, alignSelf: 'center', marginBottom: Spacing[4] },
  langModalTitle: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink, paddingHorizontal: Spacing[5], marginBottom: Spacing[3] },
  langOption: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[5], paddingVertical: Spacing[4], borderBottomWidth: 1.5, borderBottomColor: Colors.dot },
  langOptionActive: { backgroundColor: Colors.limeTint },
  langOptionText: { fontSize: 15, color: Colors.ink, fontWeight: Typography.medium },
  langOptionTextActive: { color: Colors.ink, fontWeight: Typography.bold },
  checkmark: { fontSize: 18, color: Colors.ink, fontWeight: Typography.bold },
});
