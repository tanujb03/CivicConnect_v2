import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../../src/constants/theme';
import { useAppSettings } from '../../../src/context/AppSettingsContext';

export default function AccessibilitySettingsScreen() {
  const router = useRouter();
  const { settings, setAccessibility } = useAppSettings();

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>ACCESSIBILITY</Text>
        <View style={{ width: 44 }} />
      </View>

      <View style={styles.content}>
        <Text style={styles.description}>
          Customize how CivicConnect looks and feels to suit your needs.
        </Text>

        <TouchableOpacity 
          style={styles.optionBtn}
          onPress={() => setAccessibility({ large_text: !settings.accessibility.large_text })}
        >
          <View style={styles.optionContent}>
            <Text style={styles.optionEmoji}>🔠</Text>
            <View>
              <Text style={styles.optionLabel}>Large Text Mode</Text>
              <Text style={styles.optionSub}>Increases font sizes globally</Text>
            </View>
          </View>
          <View style={[styles.checkbox, settings.accessibility.large_text && styles.checkboxActive]}>
            {settings.accessibility.large_text && <Text style={styles.checkmark}>✓</Text>}
          </View>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.optionBtn}
          onPress={() => setAccessibility({ high_contrast: !settings.accessibility.high_contrast })}
        >
          <View style={styles.optionContent}>
            <Text style={styles.optionEmoji}>🌗</Text>
            <View>
              <Text style={styles.optionLabel}>High Contrast</Text>
              <Text style={styles.optionSub}>Enhances colors and borders</Text>
            </View>
          </View>
          <View style={[styles.checkbox, settings.accessibility.high_contrast && styles.checkboxActive]}>
            {settings.accessibility.high_contrast && <Text style={styles.checkmark}>✓</Text>}
          </View>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.optionBtn}
          onPress={() => setAccessibility({ reduced_motion: !settings.accessibility.reduced_motion })}
        >
          <View style={styles.optionContent}>
            <Text style={styles.optionEmoji}>⏸️</Text>
            <View>
              <Text style={styles.optionLabel}>Reduced Motion</Text>
              <Text style={styles.optionSub}>Disables animations</Text>
            </View>
          </View>
          <View style={[styles.checkbox, settings.accessibility.reduced_motion && styles.checkboxActive]}>
            {settings.accessibility.reduced_motion && <Text style={styles.checkmark}>✓</Text>}
          </View>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4] },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  content: { paddingHorizontal: Spacing[5], paddingTop: Spacing[4] },
  description: { fontSize: 15, color: Colors.muted, marginBottom: Spacing[6], lineHeight: 22 },
  optionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], marginBottom: Spacing[3] },
  optionContent: { flexDirection: 'row', alignItems: 'center', gap: Spacing[3] },
  optionEmoji: { fontSize: 24 },
  optionLabel: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  optionSub: { fontSize: 13, color: Colors.muted, marginTop: 2 },
  checkbox: { width: 24, height: 24, borderRadius: 4, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  checkboxActive: { backgroundColor: Colors.lime },
  checkmark: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
});
