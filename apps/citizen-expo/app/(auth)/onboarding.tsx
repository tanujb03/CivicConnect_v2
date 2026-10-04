/**
 * C03 — Onboarding & Interactive Tour
 *
 * Full feature parity with Citizen Web Onboarding:
 * Phase 1: 5-Slide Interactive Feature Tour
 *   1. Spot an Issue?
 *   2. Click & Upload
 *   3. Describe the Issue
 *   4. Track Progress
 *   5. Join Community
 *
 * Phase 2: Citizen Context Setup
 *   Step 1: Display Name
 *   Step 2: Language Preference
 *   Step 3: Location / Locality
 *   Step 4: Notifications & Accessibility
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as Location from 'expo-location';
import { Colors, Typography, Spacing, Radii, Shadows } from '../../src/constants/theme';
import { useAppSettings } from '../../src/context/AppSettingsContext';
import { useAuthContext } from '../../src/context/AuthContext';
import { StatusBar } from 'expo-status-bar';

const SLIDES = [
  {
    id: 1,
    title: 'Spot an Issue?',
    subtitle: 'See civic problems in your area? We can help you report them quickly and efficiently.',
    emoji: '👁️',
    color: '#059669',
    bgColor: '#ECFDF5',
  },
  {
    id: 2,
    title: 'Click & Upload',
    subtitle: 'Capture the issue with your camera and select the problem department or category.',
    emoji: '📷',
    color: '#2563EB',
    bgColor: '#EFF6FF',
  },
  {
    id: 3,
    title: 'Describe the Issue',
    subtitle: 'Describe the issue with smart auto-complete or record a voice note up to 1 minute.',
    emoji: '🎙️',
    color: '#7C3AED',
    bgColor: '#F5F3FF',
  },
  {
    id: 4,
    title: 'Track Progress',
    subtitle: 'Track issues on the interactive city map and filter by department or resolution status.',
    emoji: '🗺️',
    color: '#D97706',
    bgColor: '#FFFBEB',
  },
  {
    id: 5,
    title: 'Join Community',
    subtitle: 'Upvote neighboring issues, verify field worker resolutions, and build a better city together.',
    emoji: '👥',
    color: '#E11D48',
    bgColor: '#FFF1F2',
  },
];

const TOTAL_SETUP_STEPS = 4;

const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिंदी' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const { settings, setLanguage, setAccessibility } = useAppSettings();

  // Mode: 'tour' (5 slides) or 'setup' (profile setup)
  const [mode, setMode] = useState<'tour' | 'setup'>('tour');
  const [currentSlide, setCurrentSlide] = useState(0);

  // Setup state
  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState('');
  const [selectedLang, setSelectedLang] = useState(settings.language);
  const [locality, setLocality] = useState('');
  const [locationStatus, setLocationStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied'>('idle');
  const [notifEnabled, setNotifEnabled] = useState(true);
  const [largeText, setLargeText] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Tour navigation
  function nextSlide() {
    if (currentSlide < SLIDES.length - 1) {
      setCurrentSlide(s => s + 1);
    } else {
      setMode('setup');
    }
  }

  function prevSlide() {
    if (currentSlide > 0) {
      setCurrentSlide(s => s - 1);
    }
  }

  function skipTour() {
    setMode('setup');
  }

  // Setup navigation
  function nextStep() {
    if (step < TOTAL_SETUP_STEPS) setStep(s => s + 1);
    else handleFinish();
  }

  function backStep() {
    if (step > 1) {
      setStep(s => s - 1);
    } else {
      setMode('tour');
    }
  }

  async function requestLocation() {
    setLocationStatus('requesting');
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        setLocationStatus('granted');
        try {
          const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
          const geo = await Location.reverseGeocodeAsync(pos.coords);
          if (geo[0]) {
            setLocality(
              [geo[0].subregion ?? geo[0].city ?? '', geo[0].district ?? ''].filter(Boolean).join(', ')
            );
          }
        } catch {
          // Manual entry fallback
        }
      } else {
        setLocationStatus('denied');
      }
    } catch {
      setLocationStatus('denied');
    }
  }

  const { authenticateAsCitizen } = useAuthContext();

  async function handleFinish() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await setLanguage(selectedLang);
      await setAccessibility({ large_text: largeText, high_contrast: highContrast });
      await authenticateAsCitizen({
        name: displayName.trim() || undefined,
        locality: locality.trim() || undefined,
        language: selectedLang,
      });
      // Ensure smooth navigation to dashboard
      router.replace('/(app)/(tabs)/dashboard');
    } catch (e) {
      console.warn('Failed to set citizen session', e);
      router.replace('/(app)/(tabs)/dashboard');
    } finally {
      setSubmitting(false);
    }
  }

  const canProceedSetup = step === 1 ? displayName.trim().length >= 2 : true;

  // ─── TOUR MODE (Slides) ────────────────────────────────────────────────
  if (mode === 'tour') {
    const slide = SLIDES[currentSlide];
    return (
      <SafeAreaView style={styles.tourContainer} edges={['top', 'bottom']}>
        <StatusBar style="dark" />

        {/* Top Bar */}
        <View style={styles.tourTopBar}>
          {currentSlide > 0 ? (
            <TouchableOpacity onPress={prevSlide} style={styles.tourNavBtn}>
              <Text style={styles.tourNavBtnText}>‹</Text>
            </TouchableOpacity>
          ) : (
            <View style={{ width: 40 }} />
          )}

          {/* Dots */}
          <View style={styles.dotsRow}>
            {SLIDES.map((_, index) => (
              <View
                key={index}
                style={[
                  styles.dot,
                  index === currentSlide ? styles.dotActive : styles.dotInactive,
                ]}
              />
            ))}
          </View>

          <TouchableOpacity onPress={skipTour} style={styles.skipBtn}>
            <Text style={styles.skipBtnText}>Skip</Text>
          </TouchableOpacity>
        </View>

        {/* Center Content */}
        <View style={styles.slideContentArea}>
          <View style={[styles.slideIconCircle, { backgroundColor: slide.bgColor, borderColor: slide.color }]}>
            <Text style={styles.slideEmoji}>{slide.emoji}</Text>
          </View>

          <Text style={styles.slideTitle}>{slide.title}</Text>
          <Text style={styles.slideSubtitle}>{slide.subtitle}</Text>
        </View>

        {/* Bottom CTA */}
        <View style={styles.tourBottomArea}>
          <TouchableOpacity
            style={[styles.tourPrimaryBtn, { backgroundColor: slide.color }]}
            onPress={nextSlide}
          >
            <Text style={styles.tourPrimaryBtnText}>
              {currentSlide === SLIDES.length - 1 ? 'Get Started →' : 'Next →'}
            </Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ─── SETUP MODE (Profile Config) ───────────────────────────────────────
  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <StatusBar style="dark" />

      {/* Progress */}
      <View style={styles.progressRow}>
        <TouchableOpacity onPress={backStep} style={styles.backBtn}>
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
        <View style={styles.progressBarTrack}>
          <View style={[styles.progressBarFill, { width: `${(step / TOTAL_SETUP_STEPS) * 100}%` }]} />
        </View>
        <Text style={styles.stepLabel}>{step}/{TOTAL_SETUP_STEPS}</Text>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {step === 1 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepEmoji}>👋</Text>
            <Text style={styles.stepTitle}>What should we call you?</Text>
            <Text style={styles.stepSub}>
              This is how you'll appear in the app. We collect only what's necessary.
            </Text>
            <TextInput
              style={styles.input}
              value={displayName}
              onChangeText={setDisplayName}
              placeholder="Your name"
              placeholderTextColor={Colors.neutral[400]}
              autoFocus
              autoCapitalize="words"
              maxLength={50}
              accessibilityLabel="Display name"
            />
            <Text style={styles.privacyNote}>
              💡 Your name is never publicly shown without your consent.
            </Text>
          </View>
        )}

        {step === 2 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepEmoji}>🌐</Text>
            <Text style={styles.stepTitle}>Preferred language</Text>
            <Text style={styles.stepSub}>
              CivicConnect will use this for notifications and AI summaries.
            </Text>
            {LANGUAGES.map(lang => (
              <TouchableOpacity
                key={lang.code}
                style={[styles.langOption, selectedLang === lang.code && styles.langOptionActive]}
                onPress={() => setSelectedLang(lang.code)}
                accessibilityRole="radio"
                accessibilityState={{ checked: selectedLang === lang.code }}
              >
                <Text style={styles.langNative}>{lang.native}</Text>
                <Text style={styles.langEnglish}>{lang.label}</Text>
                {selectedLang === lang.code && <Text style={styles.langCheck}>✓</Text>}
              </TouchableOpacity>
            ))}
          </View>
        )}

        {step === 3 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepEmoji}>📍</Text>
            <Text style={styles.stepTitle}>Your locality</Text>
            <Text style={styles.stepSub}>
              Helps us show nearby civic issues and route your reports correctly.
            </Text>

            {locationStatus !== 'granted' && (
              <TouchableOpacity
                style={styles.locationButton}
                onPress={requestLocation}
                disabled={locationStatus === 'requesting'}
                accessibilityRole="button"
                accessibilityLabel="Use my current location"
              >
                {locationStatus === 'requesting' ? (
                  <ActivityIndicator size="small" color={Colors.brand[600]} />
                ) : (
                  <Text style={styles.locationButtonText}>
                    📡 {locationStatus === 'denied' ? 'Location denied — enter manually' : 'Use my current location'}
                  </Text>
                )}
              </TouchableOpacity>
            )}

            {locationStatus === 'granted' && (
              <View style={styles.locationGranted}>
                <Text style={styles.locationGrantedText}>✅ Location access granted</Text>
              </View>
            )}

            <TextInput
              style={styles.input}
              value={locality}
              onChangeText={setLocality}
              placeholder="e.g. Main Road, Ranchi"
              placeholderTextColor={Colors.neutral[400]}
              autoCapitalize="words"
              accessibilityLabel="Locality or neighbourhood"
            />
            <Text style={styles.privacyNote}>
              💡 This is optional. You can skip it and set it from your profile later.
            </Text>

            {/* Permission explanations */}
            <View style={styles.permissionsCard}>
              <Text style={styles.permissionsTitle}>Why we need permissions</Text>
              <View style={styles.permRow}>
                <Text style={styles.permIcon}>📷</Text>
                <Text style={styles.permText}>Camera — photograph civic issues</Text>
              </View>
              <View style={styles.permRow}>
                <Text style={styles.permIcon}>🎙️</Text>
                <Text style={styles.permText}>Microphone — voice-describe issues</Text>
              </View>
              <View style={styles.permRow}>
                <Text style={styles.permIcon}>📍</Text>
                <Text style={styles.permText}>Location — attach GPS to reports</Text>
              </View>
            </View>
          </View>
        )}

        {step === 4 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepEmoji}>⚙️</Text>
            <Text style={styles.stepTitle}>Preferences</Text>
            <Text style={styles.stepSub}>
              Customise notifications and accessibility. You can change these anytime.
            </Text>

            <Text style={styles.sectionHeading}>Notifications</Text>
            <TouchableOpacity
              style={styles.toggleRow}
              onPress={() => setNotifEnabled(v => !v)}
              accessibilityRole="switch"
              accessibilityState={{ checked: notifEnabled }}
            >
              <View>
                <Text style={styles.toggleLabel}>Case updates</Text>
                <Text style={styles.toggleSub}>Status changes, assignments, resolutions</Text>
              </View>
              <View style={[styles.toggle, notifEnabled && styles.toggleOn]}>
                <View style={[styles.toggleThumb, notifEnabled && styles.toggleThumbOn]} />
              </View>
            </TouchableOpacity>

            <Text style={styles.sectionHeading}>Accessibility</Text>
            <TouchableOpacity
              style={styles.toggleRow}
              onPress={() => setLargeText(v => !v)}
              accessibilityRole="switch"
              accessibilityState={{ checked: largeText }}
            >
              <View>
                <Text style={styles.toggleLabel}>Large text mode</Text>
                <Text style={styles.toggleSub}>Increases font sizes throughout the app</Text>
              </View>
              <View style={[styles.toggle, largeText && styles.toggleOn]}>
                <View style={[styles.toggleThumb, largeText && styles.toggleThumbOn]} />
              </View>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.toggleRow}
              onPress={() => setHighContrast(v => !v)}
              accessibilityRole="switch"
              accessibilityState={{ checked: highContrast }}
            >
              <View>
                <Text style={styles.toggleLabel}>High contrast mode</Text>
                <Text style={styles.toggleSub}>Enhances border and text contrast</Text>
              </View>
              <View style={[styles.toggle, highContrast && styles.toggleOn]}>
                <View style={[styles.toggleThumb, highContrast && styles.toggleThumbOn]} />
              </View>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      {/* Setup CTA */}
      <View style={styles.ctaContainer}>
        <TouchableOpacity
          style={[styles.nextButton, !canProceedSetup && styles.nextButtonDisabled]}
          onPress={nextStep}
          disabled={!canProceedSetup || submitting}
          accessibilityRole="button"
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.nextButtonText}>
              {step === TOTAL_SETUP_STEPS ? 'Get Started →' : 'Continue →'}
            </Text>
          )}
        </TouchableOpacity>
        {step < TOTAL_SETUP_STEPS && (
          <TouchableOpacity
            onPress={handleFinish}
            accessibilityRole="button"
            accessibilityLabel="Skip setup"
          >
            <Text style={styles.skipText}>Skip for now</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.neutral[50] },

  // Tour Styles
  tourContainer: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    justifyContent: 'space-between',
  },
  tourTopBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing[5],
    paddingVertical: Spacing[4],
  },
  tourNavBtn: {
    width: 40,
    height: 40,
    borderRadius: Radii.md,
    backgroundColor: Colors.neutral[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  tourNavBtnText: {
    fontSize: 24,
    color: Colors.neutral[700],
    fontWeight: '700',
  },
  dotsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    height: 8,
    borderRadius: 4,
  },
  dotActive: {
    width: 24,
    backgroundColor: Colors.brand[600],
  },
  dotInactive: {
    width: 8,
    backgroundColor: Colors.neutral[300],
  },
  skipBtn: {
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[2],
  },
  skipBtnText: {
    fontSize: Typography.sm,
    color: Colors.neutral[500],
    fontWeight: Typography.semibold,
  },
  slideContentArea: {
    alignItems: 'center',
    paddingHorizontal: Spacing[8],
    gap: Spacing[4],
  },
  slideIconCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    marginBottom: Spacing[4],
    ...Shadows.md,
  },
  slideEmoji: {
    fontSize: 54,
  },
  slideTitle: {
    fontSize: Typography['2xl'],
    fontWeight: Typography.extrabold,
    color: Colors.neutral[900],
    textAlign: 'center',
  },
  slideSubtitle: {
    fontSize: Typography.base,
    color: Colors.neutral[600],
    textAlign: 'center',
    lineHeight: 24,
    maxWidth: 320,
  },
  tourBottomArea: {
    paddingHorizontal: Spacing[6],
    paddingBottom: Spacing[6],
  },
  tourPrimaryBtn: {
    paddingVertical: Spacing[4],
    borderRadius: Radii.xl,
    alignItems: 'center',
    ...Shadows.civic,
  },
  tourPrimaryBtnText: {
    color: '#FFFFFF',
    fontSize: Typography.base,
    fontWeight: Typography.bold,
  },

  // Setup Styles
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[3],
    gap: Spacing[3],
  },
  backBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  backBtnText: { fontSize: 22, color: Colors.neutral[700] },
  progressBarTrack: {
    flex: 1,
    height: 4,
    backgroundColor: Colors.neutral[200],
    borderRadius: Radii.full,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: Colors.brand[500],
    borderRadius: Radii.full,
  },
  stepLabel: { fontSize: Typography.xs, color: Colors.neutral[500], fontWeight: Typography.medium, width: 28 },
  scrollContent: { paddingHorizontal: Spacing[6], paddingBottom: Spacing[4] },
  stepContent: { paddingTop: Spacing[4] },
  stepEmoji: { fontSize: 48, marginBottom: Spacing[3] },
  stepTitle: {
    fontSize: Typography['2xl'],
    fontWeight: Typography.extrabold,
    color: Colors.neutral[900],
    letterSpacing: -0.6,
    marginBottom: Spacing[2],
  },
  stepSub: {
    fontSize: Typography.base,
    color: Colors.neutral[500],
    lineHeight: 22,
    marginBottom: Spacing[6],
  },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1.5,
    borderColor: Colors.brand[200],
    borderRadius: Radii.lg,
    paddingHorizontal: Spacing[4],
    paddingVertical: Spacing[4],
    fontSize: Typography.base,
    color: Colors.neutral[900],
    marginBottom: Spacing[3],
    ...Shadows.sm,
  },
  privacyNote: {
    fontSize: Typography.sm,
    color: Colors.neutral[400],
    lineHeight: 18,
  },
  langOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderWidth: 1.5,
    borderColor: Colors.neutral[200],
    borderRadius: Radii.lg,
    paddingHorizontal: Spacing[4],
    paddingVertical: Spacing[3.5],
    marginBottom: Spacing[2],
    gap: Spacing[3],
  },
  langOptionActive: {
    borderColor: Colors.brand[400],
    backgroundColor: Colors.brand[50],
  },
  langNative: { fontSize: Typography.md, fontWeight: Typography.bold, color: Colors.neutral[900], flex: 1 },
  langEnglish: { fontSize: Typography.sm, color: Colors.neutral[500] },
  langCheck: { fontSize: Typography.lg, color: Colors.brand[600] },
  locationButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.brand[50],
    borderWidth: 1.5,
    borderColor: Colors.brand[200],
    borderRadius: Radii.lg,
    paddingVertical: Spacing[3.5],
    marginBottom: Spacing[4],
    gap: Spacing[2],
  },
  locationButtonText: { fontSize: Typography.base, color: Colors.brand[700], fontWeight: Typography.semibold },
  locationGranted: {
    backgroundColor: '#ecfdf5',
    borderRadius: Radii.md,
    paddingVertical: Spacing[2.5],
    paddingHorizontal: Spacing[4],
    marginBottom: Spacing[3],
  },
  locationGrantedText: { fontSize: Typography.sm, color: Colors.success, fontWeight: Typography.medium },
  permissionsCard: {
    backgroundColor: Colors.neutral[100],
    borderRadius: Radii.lg,
    padding: Spacing[4],
    marginTop: Spacing[4],
    gap: Spacing[3],
  },
  permissionsTitle: { fontSize: Typography.sm, fontWeight: Typography.semibold, color: Colors.neutral[700], marginBottom: Spacing[1] },
  permRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing[3] },
  permIcon: { fontSize: 18 },
  permText: { fontSize: Typography.sm, color: Colors.neutral[600], flex: 1 },
  sectionHeading: {
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
    color: Colors.neutral[600],
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginTop: Spacing[5],
    marginBottom: Spacing[3],
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#fff',
    borderRadius: Radii.lg,
    padding: Spacing[4],
    marginBottom: Spacing[2],
    borderWidth: 1,
    borderColor: Colors.neutral[200],
  },
  toggleLabel: { fontSize: Typography.base, fontWeight: Typography.semibold, color: Colors.neutral[900] },
  toggleSub: { fontSize: Typography.xs, color: Colors.neutral[400], marginTop: 2 },
  toggle: {
    width: 48,
    height: 28,
    borderRadius: Radii.full,
    backgroundColor: Colors.neutral[300],
    justifyContent: 'center',
    paddingHorizontal: 3,
  },
  toggleOn: { backgroundColor: Colors.brand[500] },
  toggleThumb: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#fff',
    ...Shadows.sm,
  },
  toggleThumbOn: { alignSelf: 'flex-end' },
  ctaContainer: {
    paddingHorizontal: Spacing[6],
    paddingBottom: Spacing[6],
    gap: Spacing[3],
  },
  nextButton: {
    backgroundColor: Colors.brand[600],
    borderRadius: Radii.xl,
    paddingVertical: Spacing[4],
    alignItems: 'center',
    ...Shadows.civic,
  },
  nextButtonDisabled: {
    backgroundColor: Colors.neutral[300],
    shadowOpacity: 0,
  },
  nextButtonText: {
    color: '#fff',
    fontSize: Typography.base,
    fontWeight: Typography.bold,
  },
  skipText: {
    color: Colors.neutral[400],
    fontSize: Typography.sm,
    fontWeight: Typography.medium,
    textAlign: 'center',
  },
});
