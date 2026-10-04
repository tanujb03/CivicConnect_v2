/**
 * C01 — Welcome
 *
 * First-touch entry point.
 * - CivicConnect logo + mission statement
 * - civic workflow visual
 * - Get Started CTA → onboarding
 * - I already have an account → login
 * - Language selector
 * - Accessibility shortcut
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Dimensions,
  Modal,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../src/constants/theme';
import { useAppSettings } from '../../src/context/AppSettingsContext';
import { StatusBar } from 'expo-status-bar';

const { width } = Dimensions.get('window');

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

// Workflow steps shown in the center visual
const WORKFLOW_STEPS = [
  { icon: '📸', label: 'Spot the issue', color: '#3b82f6' },
  { icon: '📍', label: 'Report with location', color: '#f59e0b' },
  { icon: '🤖', label: 'AI classifies it', color: '#8b5cf6' },
  { icon: '🏛️', label: 'City acts on it', color: '#10b981' },
  { icon: '✅', label: 'You verify resolution', color: Colors.brand[600] },
];

export default function WelcomeScreen() {
  const router = useRouter();
  const { settings, setLanguage } = useAppSettings();
  const [showLangModal, setShowLangModal] = useState(false);

  const currentLang = LANGUAGES.find(l => l.code === settings.language) ?? LANGUAGES[0];

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <StatusBar style="light" />

      {/* Header bar */}
      <View style={styles.topBar}>
        <View style={styles.logoRow}>
          <View style={styles.logoBox}>
            <Text style={styles.logoEmoji}>🏙️</Text>
          </View>
          <View>
            <Text style={styles.appName}>CivicConnect</Text>
            <Text style={styles.appVersion}>v2</Text>
          </View>
        </View>

        <TouchableOpacity
          onPress={() => setShowLangModal(true)}
          style={styles.langButton}
          accessibilityLabel={`Language: ${currentLang.label}. Tap to change.`}
          accessibilityRole="button"
        >
          <Text style={styles.langButtonText}>🌐 {currentLang.label}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Mission */}
        <View style={styles.missionSection}>
          <Text style={styles.missionHeadline}>
            Your city, your{'\n'}voice, your change.
          </Text>
          <Text style={styles.missionSub}>
            Report civic issues. Track their resolution. Build a better city — together.
          </Text>
        </View>

        {/* Workflow visual */}
        <View style={styles.workflowCard}>
          <Text style={styles.workflowTitle}>How it works</Text>
          {WORKFLOW_STEPS.map((step, index) => (
            <View key={index} style={styles.workflowRow}>
              <View style={[styles.stepIconBox, { backgroundColor: step.color + '20' }]}>
                <Text style={styles.stepEmoji}>{step.icon}</Text>
              </View>
              <Text style={styles.stepLabel}>{step.label}</Text>
              {index < WORKFLOW_STEPS.length - 1 && (
                <View style={styles.stepConnector} />
              )}
            </View>
          ))}
        </View>

        {/* Trust indicators */}
        <View style={styles.trustRow}>
          <View style={styles.trustItem}>
            <Text style={styles.trustNumber}>AI</Text>
            <Text style={styles.trustLabel}>Smart triage</Text>
          </View>
          <View style={styles.trustDivider} />
          <View style={styles.trustItem}>
            <Text style={styles.trustNumber}>📶</Text>
            <Text style={styles.trustLabel}>Works offline</Text>
          </View>
          <View style={styles.trustDivider} />
          <View style={styles.trustItem}>
            <Text style={styles.trustNumber}>🔒</Text>
            <Text style={styles.trustLabel}>Secure</Text>
          </View>
        </View>
      </ScrollView>

      {/* CTAs */}
      <View style={styles.ctaSection}>
        <TouchableOpacity
          style={styles.primaryCta}
          onPress={() => router.push('/(auth)/onboarding')}
          accessibilityRole="button"
          accessibilityLabel="Get Started"
        >
          <Text style={styles.primaryCtaText}>Get Started</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.secondaryCta}
          onPress={() => router.push('/(auth)/login')}
          accessibilityRole="button"
          accessibilityLabel="I already have an account"
        >
          <Text style={styles.secondaryCtaText}>I already have an account</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.a11yButton}
          onPress={() => router.push('/(app)/settings/accessibility')}
          accessibilityRole="button"
          accessibilityLabel="Accessibility settings"
        >
          <Text style={styles.a11yText}>♿ Accessibility</Text>
        </TouchableOpacity>
      </View>

      {/* Language Modal */}
      <Modal
        visible={showLangModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowLangModal(false)}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowLangModal(false)}
        >
          <View style={styles.langModal}>
            <View style={styles.langModalHandle} />
            <Text style={styles.langModalTitle}>Select Language</Text>
            <FlatList
              data={LANGUAGES}
              keyExtractor={item => item.code}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.langOption,
                    item.code === settings.language && styles.langOptionActive,
                  ]}
                  onPress={async () => {
                    await setLanguage(item.code);
                    setShowLangModal(false);
                  }}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: item.code === settings.language }}
                >
                  <Text style={[
                    styles.langOptionText,
                    item.code === settings.language && styles.langOptionTextActive,
                  ]}>
                    {item.label}
                  </Text>
                  {item.code === settings.language && (
                    <Text style={styles.checkmark}>✓</Text>
                  )}
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
  container: {
    flex: 1,
    backgroundColor: Colors.brand[800],
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[3],
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3],
  },
  logoBox: {
    width: 40,
    height: 40,
    borderRadius: Radii.md,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoEmoji: { fontSize: 22 },
  appName: {
    color: '#fff',
    fontSize: Typography.md,
    fontWeight: Typography.bold,
    letterSpacing: -0.5,
  },
  appVersion: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: Typography.xs,
    fontWeight: Typography.medium,
  },
  langButton: {
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.15)',
  },
  langButtonText: {
    color: '#fff',
    fontSize: Typography.sm,
    fontWeight: Typography.medium,
  },
  scrollContent: {
    paddingHorizontal: Spacing[5],
    paddingBottom: Spacing[4],
  },
  missionSection: {
    marginTop: Spacing[6],
    marginBottom: Spacing[6],
  },
  missionHeadline: {
    color: '#fff',
    fontSize: Typography['3xl'],
    fontWeight: Typography.extrabold,
    lineHeight: 38,
    letterSpacing: -0.8,
    marginBottom: Spacing[3],
  },
  missionSub: {
    color: 'rgba(255,255,255,0.65)',
    fontSize: Typography.base,
    lineHeight: 22,
  },
  workflowCard: {
    backgroundColor: 'rgba(255,255,255,0.10)',
    borderRadius: Radii.xl,
    padding: Spacing[5],
    marginBottom: Spacing[5],
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  workflowTitle: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: Spacing[4],
  },
  workflowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3],
    marginBottom: Spacing[1],
    position: 'relative',
  },
  stepIconBox: {
    width: 40,
    height: 40,
    borderRadius: Radii.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepEmoji: { fontSize: 20 },
  stepLabel: {
    color: '#fff',
    fontSize: Typography.base,
    fontWeight: Typography.medium,
    flex: 1,
  },
  stepConnector: {
    position: 'absolute',
    left: 19,
    bottom: -8,
    width: 2,
    height: 16,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  trustRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: Radii.lg,
    paddingVertical: Spacing[4],
    paddingHorizontal: Spacing[3],
  },
  trustItem: { alignItems: 'center', flex: 1 },
  trustNumber: {
    color: '#fff',
    fontSize: Typography.lg,
    fontWeight: Typography.bold,
    marginBottom: Spacing[0.5],
  },
  trustLabel: {
    color: 'rgba(255,255,255,0.55)',
    fontSize: Typography.xs,
    fontWeight: Typography.medium,
    textAlign: 'center',
  },
  trustDivider: {
    width: 1,
    height: 32,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  ctaSection: {
    paddingHorizontal: Spacing[5],
    paddingBottom: Spacing[6],
    gap: Spacing[3],
  },
  primaryCta: {
    backgroundColor: '#fff',
    borderRadius: Radii.xl,
    paddingVertical: Spacing[4],
    alignItems: 'center',
  },
  primaryCtaText: {
    color: Colors.brand[800],
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    letterSpacing: -0.3,
  },
  secondaryCta: {
    borderRadius: Radii.xl,
    paddingVertical: Spacing[4],
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  secondaryCtaText: {
    color: '#fff',
    fontSize: Typography.base,
    fontWeight: Typography.semibold,
  },
  a11yButton: {
    alignItems: 'center',
    paddingVertical: Spacing[2],
  },
  a11yText: {
    color: 'rgba(255,255,255,0.45)',
    fontSize: Typography.sm,
    fontWeight: Typography.medium,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  langModal: {
    backgroundColor: '#fff',
    borderTopLeftRadius: Radii['2xl'],
    borderTopRightRadius: Radii['2xl'],
    paddingTop: Spacing[3],
    paddingBottom: Spacing[10],
    maxHeight: '70%',
  },
  langModalHandle: {
    width: 36,
    height: 4,
    backgroundColor: Colors.neutral[300],
    borderRadius: Radii.full,
    alignSelf: 'center',
    marginBottom: Spacing[4],
  },
  langModalTitle: {
    fontSize: Typography.lg,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    paddingHorizontal: Spacing[5],
    marginBottom: Spacing[3],
  },
  langOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing[5],
    paddingVertical: Spacing[4],
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[100],
  },
  langOptionActive: {
    backgroundColor: Colors.brand[50],
  },
  langOptionText: {
    fontSize: Typography.base,
    color: Colors.neutral[700],
    fontWeight: Typography.medium,
  },
  langOptionTextActive: {
    color: Colors.brand[700],
    fontWeight: Typography.bold,
  },
  checkmark: {
    fontSize: Typography.lg,
    color: Colors.brand[600],
    fontWeight: Typography.bold,
  },
});
