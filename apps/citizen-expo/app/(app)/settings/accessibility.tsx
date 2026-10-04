/**
 * C14 — Accessibility Settings
 *
 * Configures:
 * - Large Text
 * - High Contrast
 * - Reduced Motion
 * - Simplified Language Mode (plain-language AI summaries)
 * - Voice Playback (audio readout of case updates)
 * - Screen Reader optimization
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
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

export default function AccessibilitySettingsScreen() {
  const router = useRouter();
  const { settings, setAccessibility } = useAppSettings();
  const a11y = settings.accessibility;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Back to Profile"
        >
          <Text style={styles.backBtnText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Accessibility</Text>
        <View style={{ width: 44 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Intro */}
        <View style={styles.banner}>
          <Text style={styles.bannerEmoji}>♿</Text>
          <View style={styles.bannerTextContainer}>
            <Text style={styles.bannerTitle}>Inclusive Civic Access</Text>
            <Text style={styles.bannerBody}>
              CivicConnect is built for everyone. Adjust visual, auditory, and language preferences to suit your needs.
            </Text>
          </View>
        </View>

        {/* Visual Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Visual & Display</Text>

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Large Text Mode</Text>
              <Text style={styles.toggleDesc}>
                Increases font sizes throughout case details, timelines, and reporting forms.
              </Text>
            </View>
            <Switch
              value={a11y.large_text}
              onValueChange={v => setAccessibility({ large_text: v })}
              trackColor={{ false: Colors.neutral[300], true: Colors.brand[600] }}
            />
          </View>

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>High Contrast</Text>
              <Text style={styles.toggleDesc}>
                Maximizes contrast between text and background borders for easier readability outdoors.
              </Text>
            </View>
            <Switch
              value={a11y.high_contrast}
              onValueChange={v => setAccessibility({ high_contrast: v })}
              trackColor={{ false: Colors.neutral[300], true: Colors.brand[600] }}
            />
          </View>

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Reduced Motion</Text>
              <Text style={styles.toggleDesc}>
                Disables non-essential animations and transitions for sensitive users.
              </Text>
            </View>
            <Switch
              value={a11y.reduced_motion}
              onValueChange={v => setAccessibility({ reduced_motion: v })}
              trackColor={{ false: Colors.neutral[300], true: Colors.brand[600] }}
            />
          </View>
        </View>

        {/* Language & Comprehension */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Language & Audio</Text>

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Simplified Language Mode</Text>
              <Text style={styles.toggleDesc}>
                AI generates concise, plain-language summaries without municipal jargon or technical codes.
              </Text>
            </View>
            <Switch
              value={a11y.simplified_language}
              onValueChange={v => setAccessibility({ simplified_language: v })}
              trackColor={{ false: Colors.neutral[300], true: Colors.brand[600] }}
            />
          </View>

          <View style={styles.toggleRow}>
            <View style={styles.toggleInfo}>
              <Text style={styles.toggleLabel}>Voice Readout / Audio Assist</Text>
              <Text style={styles.toggleDesc}>
                Automatically provides audio playback buttons for status updates and AI situation briefs.
              </Text>
            </View>
            <Switch
              value={a11y.voice_playback}
              onValueChange={v => setAccessibility({ voice_playback: v })}
              trackColor={{ false: Colors.neutral[300], true: Colors.brand[600] }}
            />
          </View>
        </View>

        {/* Quick Link to Language */}
        <TouchableOpacity
          style={styles.languageLinkCard}
          onPress={() => router.push('/(app)/settings/language')}
        >
          <View>
            <Text style={styles.languageLinkTitle}>Regional Language Settings</Text>
            <Text style={styles.languageLinkSub}>
              Switch interface to Kannada (ಕನ್ನಡ), Hindi (हिंदी), or English
            </Text>
          </View>
          <Text style={styles.arrowIcon}>›</Text>
        </TouchableOpacity>
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
    paddingBottom: Spacing.xxl * 2,
  },
  banner: {
    flexDirection: 'row',
    backgroundColor: Colors.brand[50],
    padding: Spacing.lg,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.brand[200],
    gap: Spacing.md,
    alignItems: 'center',
  },
  bannerEmoji: {
    fontSize: 32,
  },
  bannerTextContainer: {
    flex: 1,
    gap: 2,
  },
  bannerTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: Colors.brand[900],
  },
  bannerBody: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.brand[800],
    lineHeight: 18,
  },
  section: {
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.md,
    ...Shadows.sm,
  },
  sectionTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: Typography.titleSmall.fontWeight,
    color: Colors.neutral[900],
    marginBottom: Spacing.xs,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[100],
    gap: Spacing.md,
  },
  toggleInfo: {
    flex: 1,
    gap: 2,
  },
  toggleLabel: {
    fontSize: Typography.bodyMedium.fontSize,
    fontWeight: '600',
    color: Colors.neutral[800],
  },
  toggleDesc: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
    lineHeight: 18,
  },
  languageLinkCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    ...Shadows.sm,
  },
  languageLinkTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '600',
    color: Colors.neutral[900],
  },
  languageLinkSub: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
    marginTop: 2,
  },
  arrowIcon: {
    fontSize: 24,
    color: Colors.neutral[400],
  },
});
