/**
 * C14 (Part 2) — Language Settings
 *
 * Configures application language across UI, AI summaries, notifications,
 * and voice interaction.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import {
  Colors,
  Typography,
  Spacing,
  Radii,
  Shadows,
} from '../../../src/constants/theme';
import { useAppSettings } from '../../../src/context/AppSettingsContext';

interface LanguageOption {
  code: string;
  name: string;
  nativeName: string;
  region: string;
}

const SUPPORTED_LANGUAGES: LanguageOption[] = [
  { code: 'en', name: 'English', nativeName: 'English', region: 'Default' },
  { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ', region: 'Karnataka / State' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी', region: 'National' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', region: 'Regional' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు', region: 'Regional' },
];

export default function LanguageSettingsScreen() {
  const router = useRouter();
  const { settings, setLanguage } = useAppSettings();

  const handleSelectLanguage = async (code: string) => {
    await setLanguage(code);
    router.back();
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Back"
        >
          <Text style={styles.backBtnText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Select Language</Text>
        <View style={{ width: 44 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.infoBanner}>
          <Text style={styles.infoIcon}>🌐</Text>
          <Text style={styles.infoText}>
            Selected language applies to navigation labels, AI intake summaries, voice interactions, and departmental status notifications.
          </Text>
        </View>

        <View style={styles.card}>
          {SUPPORTED_LANGUAGES.map((lang, index) => {
            const isSelected = settings.language === lang.code;
            return (
              <TouchableOpacity
                key={lang.code}
                style={[
                  styles.optionRow,
                  index < SUPPORTED_LANGUAGES.length - 1 && styles.borderBottom,
                  isSelected && styles.optionRowSelected,
                ]}
                onPress={() => handleSelectLanguage(lang.code)}
                accessibilityRole="radio"
                accessibilityState={{ selected: isSelected }}
              >
                <View style={styles.optionLeft}>
                  <Text style={[styles.nativeText, isSelected && styles.selectedColor]}>
                    {lang.nativeName}
                  </Text>
                  <Text style={styles.englishName}>
                    {lang.name} • {lang.region}
                  </Text>
                </View>

                <View style={[styles.radioCircle, isSelected && styles.radioCircleActive]}>
                  {isSelected && <View style={styles.radioInner} />}
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.neutral[50],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
  },
  backBtn: {
    padding: Spacing.sm,
  },
  backBtnText: {
    fontSize: Typography.bodyLarge.fontSize,
    color: Colors.brand[600],
    fontWeight: '600',
  },
  headerTitle: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: Typography.titleMedium.fontWeight,
    color: Colors.neutral[900],
  },
  scrollContent: {
    padding: Spacing.lg,
    gap: Spacing.lg,
  },
  infoBanner: {
    flexDirection: 'row',
    backgroundColor: Colors.brand[50],
    padding: Spacing.md,
    borderRadius: Radii.md,
    alignItems: 'center',
    gap: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.brand[200],
  },
  infoIcon: {
    fontSize: 24,
  },
  infoText: {
    flex: 1,
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.brand[800],
    lineHeight: 18,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    ...Shadows.sm,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.lg,
  },
  optionRowSelected: {
    backgroundColor: Colors.brand[50],
  },
  borderBottom: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[100],
  },
  optionLeft: {
    gap: 2,
  },
  nativeText: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  selectedColor: {
    color: Colors.brand[700],
  },
  englishName: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
  },
  radioCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: Colors.neutral[300],
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioCircleActive: {
    borderColor: Colors.brand[600],
  },
  radioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: Colors.brand[600],
  },
});
