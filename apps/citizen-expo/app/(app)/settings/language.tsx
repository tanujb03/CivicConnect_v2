import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, FlatList } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../../src/constants/theme';
import { useAppSettings } from '../../../src/context/AppSettingsContext';

const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिंदी' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
];

export default function LanguageSettingsScreen() {
  const router = useRouter();
  const { settings, setLanguage } = useAppSettings();

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>LANGUAGE</Text>
        <View style={{ width: 44 }} />
      </View>

      <FlatList
        data={LANGUAGES}
        keyExtractor={item => item.code}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => {
          const isActive = settings.language === item.code;
          return (
            <TouchableOpacity 
              style={[styles.langBtn, isActive && styles.langBtnActive]}
              onPress={() => setLanguage(item.code)}
            >
              <View>
                <Text style={styles.langNative}>{item.native}</Text>
                <Text style={styles.langLabel}>{item.label}</Text>
              </View>
              <View style={[styles.radio, isActive && styles.radioActive]}>
                {isActive && <View style={styles.radioInner} />}
              </View>
            </TouchableOpacity>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4] },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  list: { paddingHorizontal: Spacing[5], paddingTop: Spacing[4] },
  langBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], marginBottom: Spacing[3] },
  langBtnActive: { backgroundColor: Colors.limeTint },
  langNative: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink },
  langLabel: { fontSize: 13, color: Colors.muted, marginTop: 2 },
  radio: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  radioActive: { borderColor: Colors.ink },
  radioInner: { width: 12, height: 12, borderRadius: 6, backgroundColor: Colors.ink },
});
