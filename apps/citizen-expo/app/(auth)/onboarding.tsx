import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as Location from 'expo-location';
import { Colors, Typography, Spacing, Radii } from '../../src/constants/theme';
import { useAppSettings } from '../../src/context/AppSettingsContext';
import { useAuthContext } from '../../src/context/AuthContext';
import { StatusBar } from 'expo-status-bar';

const SLIDES = [
  { id: 1, title: 'SPOT AN ISSUE?', subtitle: 'See civic problems in your area? Report them quickly.', emoji: '👁️', color: Colors.lime },
  { id: 2, title: 'CLICK & UPLOAD', subtitle: 'Capture the issue with your camera.', emoji: '📷', color: Colors.amber },
  { id: 3, title: 'DESCRIBE', subtitle: 'Use smart auto-complete or record a voice note.', emoji: '🎙️', color: Colors.wine },
  { id: 4, title: 'TRACK PROGRESS', subtitle: 'Track issues on the interactive city map.', emoji: '🗺️', color: Colors.fire },
  { id: 5, title: 'JOIN COMMUNITY', subtitle: 'Upvote neighboring issues and verify resolutions.', emoji: '👥', color: Colors.limeTint },
];

const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिंदी' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const { settings, setLanguage, setAccessibility } = useAppSettings();
  const { authenticateAsCitizen } = useAuthContext();

  const [mode, setMode] = useState<'tour' | 'setup'>('tour');
  const [currentSlide, setCurrentSlide] = useState(0);

  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState('');
  const [selectedLang, setSelectedLang] = useState(settings.language);
  const [locality, setLocality] = useState('');
  const [locationStatus, setLocationStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied'>('idle');
  const [notifEnabled, setNotifEnabled] = useState(true);
  const [largeText, setLargeText] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function nextSlide() { currentSlide < SLIDES.length - 1 ? setCurrentSlide(s => s + 1) : setMode('setup'); }
  function prevSlide() { if (currentSlide > 0) setCurrentSlide(s => s - 1); }
  function skipTour() { setMode('setup'); }
  function nextStep() { step < 4 ? setStep(s => s + 1) : handleFinish(); }
  function backStep() { step > 1 ? setStep(s => s - 1) : setMode('tour'); }

  async function requestLocation() {
    setLocationStatus('requesting');
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        setLocationStatus('granted');
        const pos = await Location.getCurrentPositionAsync({});
        const geo = await Location.reverseGeocodeAsync(pos.coords);
        if (geo[0]) setLocality([geo[0].city ?? '', geo[0].district ?? ''].filter(Boolean).join(', '));
      } else {
        setLocationStatus('denied');
      }
    } catch {
      setLocationStatus('denied');
    }
  }

  async function handleFinish() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await setLanguage(selectedLang);
      await setAccessibility({ large_text: largeText, high_contrast: highContrast, reduced_motion: false });
      await authenticateAsCitizen({ name: displayName.trim() || undefined, locality: locality.trim() || undefined, language: selectedLang });
      router.replace('/(app)/(tabs)/dashboard');
    } catch {
      router.replace('/(app)/(tabs)/dashboard');
    } finally {
      setSubmitting(false);
    }
  }

  const canProceed = step === 1 ? displayName.trim().length >= 2 : true;

  if (mode === 'tour') {
    const slide = SLIDES[currentSlide];
    return (
      <SafeAreaView style={styles.tourContainer} edges={['top', 'bottom']}>
        <StatusBar style="dark" />
        <View style={styles.tourTopBar}>
          {currentSlide > 0 ? (
            <TouchableOpacity onPress={prevSlide} style={styles.navBtn}><Text style={styles.navBtnText}>←</Text></TouchableOpacity>
          ) : <View style={{ width: 44 }} />}
          <TouchableOpacity onPress={skipTour} style={styles.skipBtn}><Text style={styles.skipBtnText}>Skip</Text></TouchableOpacity>
        </View>

        <View style={styles.slideContent}>
          <View style={styles.iconContainer}>
            <View style={styles.iconShadow} />
            <View style={[styles.iconCard, { backgroundColor: slide.color }]}>
              <Text style={styles.slideEmoji}>{slide.emoji}</Text>
            </View>
          </View>
          <Text style={styles.slideTitle}>{slide.title}</Text>
          <Text style={styles.slideSubtitle}>{slide.subtitle}</Text>
        </View>

        <View style={styles.tourBottom}>
          <View style={styles.dotsRow}>
            {SLIDES.map((_, i) => (
              <View key={i} style={[styles.dot, i === currentSlide && styles.dotActive]} />
            ))}
          </View>
          <View style={styles.nextBtnContainer}>
            <View style={styles.nextBtnShadow} />
            <TouchableOpacity style={styles.nextBtn} onPress={nextSlide}>
              <Text style={styles.nextBtnText}>{currentSlide === SLIDES.length - 1 ? 'Start Setup' : 'Next'} →</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <StatusBar style="dark" />
      <View style={styles.progressRow}>
        <TouchableOpacity onPress={backStep} style={styles.navBtn}><Text style={styles.navBtnText}>←</Text></TouchableOpacity>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${(step / 4) * 100}%` }]} />
        </View>
        <Text style={styles.stepLabel}>{step}/4</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.scrollContent}>
        {step === 1 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepTitle}>YOUR NAME?</Text>
            <Text style={styles.stepSub}>We collect only what's necessary.</Text>
            <View style={styles.inputOuter}>
              <View style={styles.inputShadow} />
              <TextInput style={styles.input} value={displayName} onChangeText={setDisplayName} placeholder="E.g. Ramesh Kumar" placeholderTextColor={Colors.muted} autoFocus />
            </View>
          </View>
        )}
        {step === 2 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepTitle}>LANGUAGE?</Text>
            <Text style={styles.stepSub}>Select your preferred app language.</Text>
            {LANGUAGES.map(lang => (
              <TouchableOpacity key={lang.code} style={[styles.optionCard, selectedLang === lang.code && styles.optionCardActive]} onPress={() => setSelectedLang(lang.code)}>
                <Text style={styles.optionTitle}>{lang.native} ({lang.label})</Text>
                {selectedLang === lang.code && <Text style={styles.checkmark}>✓</Text>}
              </TouchableOpacity>
            ))}
          </View>
        )}
        {step === 3 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepTitle}>YOUR LOCALITY?</Text>
            <Text style={styles.stepSub}>Helps us show nearby issues.</Text>
            {locationStatus !== 'granted' ? (
              <TouchableOpacity style={styles.locBtn} onPress={requestLocation}>
                <Text style={styles.locBtnText}>{locationStatus === 'requesting' ? 'Requesting...' : '📍 Use Current Location'}</Text>
              </TouchableOpacity>
            ) : <Text style={styles.grantedText}>✅ Location granted</Text>}
            <View style={styles.inputOuter}>
              <View style={styles.inputShadow} />
              <TextInput style={styles.input} value={locality} onChangeText={setLocality} placeholder="e.g. Main Road, Ranchi" placeholderTextColor={Colors.muted} />
            </View>
          </View>
        )}
        {step === 4 && (
          <View style={styles.stepContent}>
            <Text style={styles.stepTitle}>PREFERENCES</Text>
            <Text style={styles.stepSub}>Customize your experience.</Text>
            <TouchableOpacity style={styles.toggleRow} onPress={() => setNotifEnabled(!notifEnabled)}>
              <Text style={styles.toggleLabel}>Enable Notifications</Text>
              <View style={[styles.toggleBox, notifEnabled && styles.toggleBoxActive]}>{notifEnabled && <Text style={styles.checkmark}>✓</Text>}</View>
            </TouchableOpacity>
            <TouchableOpacity style={styles.toggleRow} onPress={() => setLargeText(!largeText)}>
              <Text style={styles.toggleLabel}>Large Text Mode</Text>
              <View style={[styles.toggleBox, largeText && styles.toggleBoxActive]}>{largeText && <Text style={styles.checkmark}>✓</Text>}</View>
            </TouchableOpacity>
            <TouchableOpacity style={styles.toggleRow} onPress={() => setHighContrast(!highContrast)}>
              <Text style={styles.toggleLabel}>High Contrast Mode</Text>
              <View style={[styles.toggleBox, highContrast && styles.toggleBoxActive]}>{highContrast && <Text style={styles.checkmark}>✓</Text>}</View>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      <View style={styles.bottomArea}>
        <View style={styles.nextBtnContainer}>
          <View style={styles.nextBtnShadow} />
          <TouchableOpacity style={[styles.nextBtn, !canProceed && styles.nextBtnDisabled]} onPress={nextStep} disabled={!canProceed || submitting}>
            {submitting ? <ActivityIndicator color={Colors.ink} /> : <Text style={styles.nextBtnText}>{step === 4 ? 'Finish Setup' : 'Continue'} →</Text>}
          </TouchableOpacity>
        </View>
        {step < 4 && <TouchableOpacity onPress={handleFinish} style={styles.skipSetupBtn}><Text style={styles.skipSetupText}>Skip setup</Text></TouchableOpacity>}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.ground },
  tourContainer: { flex: 1, backgroundColor: Colors.ground },
  tourTopBar: { flexDirection: 'row', justifyContent: 'space-between', padding: Spacing[4] },
  navBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  navBtnText: { fontSize: 18, color: Colors.ink },
  skipBtn: { padding: Spacing[2] },
  skipBtnText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.muted, textDecorationLine: 'underline' },
  slideContent: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Spacing[6] },
  iconContainer: { marginBottom: Spacing[6] },
  iconShadow: { position: 'absolute', top: 6, left: 6, right: -6, bottom: -6, backgroundColor: Colors.ink, borderRadius: Radii.xl },
  iconCard: { width: 140, height: 140, borderRadius: Radii.xl, alignItems: 'center', justifyContent: 'center', borderWidth: 3, borderColor: Colors.ink },
  slideEmoji: { fontSize: 64 },
  slideTitle: { fontSize: 36, fontWeight: Typography.black, color: Colors.ink, textAlign: 'center', marginBottom: Spacing[3], letterSpacing: -1 },
  slideSubtitle: { fontSize: 16, color: Colors.muted, textAlign: 'center', lineHeight: 24 },
  tourBottom: { padding: Spacing[6] },
  dotsRow: { flexDirection: 'row', justifyContent: 'center', gap: Spacing[2], marginBottom: Spacing[6] },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: Colors.dot, borderWidth: 1, borderColor: Colors.ink },
  dotActive: { width: 24, backgroundColor: Colors.ink },
  nextBtnContainer: { width: '100%' },
  nextBtnShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  nextBtn: { backgroundColor: Colors.lime, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, paddingVertical: Spacing[4], alignItems: 'center' },
  nextBtnText: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink },
  nextBtnDisabled: { backgroundColor: Colors.dot },
  progressRow: { flexDirection: 'row', alignItems: 'center', padding: Spacing[4], gap: Spacing[3] },
  progressBar: { flex: 1, height: 8, backgroundColor: Colors.surface, borderWidth: 1.5, borderColor: Colors.ink, borderRadius: 4 },
  progressFill: { height: '100%', backgroundColor: Colors.ink },
  stepLabel: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  scrollContent: { padding: Spacing[6] },
  stepContent: { paddingTop: Spacing[2] },
  stepTitle: { fontSize: 36, fontWeight: Typography.black, color: Colors.ink, marginBottom: Spacing[2], letterSpacing: -1 },
  stepSub: { fontSize: 16, color: Colors.muted, marginBottom: Spacing[6] },
  inputOuter: { marginBottom: Spacing[4] },
  inputShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  input: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], fontSize: 16, color: Colors.ink },
  optionCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], marginBottom: Spacing[3] },
  optionCardActive: { backgroundColor: Colors.limeTint },
  optionTitle: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  checkmark: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink },
  locBtn: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], alignItems: 'center', marginBottom: Spacing[4] },
  locBtnText: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  grantedText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.lime, marginBottom: Spacing[4] },
  toggleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], marginBottom: Spacing[3] },
  toggleLabel: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  toggleBox: { width: 24, height: 24, borderRadius: 4, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  toggleBoxActive: { backgroundColor: Colors.lime },
  bottomArea: { padding: Spacing[6] },
  skipSetupBtn: { marginTop: Spacing[4], alignItems: 'center' },
  skipSetupText: { fontSize: 14, fontWeight: Typography.bold, color: Colors.muted, textDecorationLine: 'underline' },
});
