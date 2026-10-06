import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../../src/constants/theme';

export default function ExpandedMapScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>✕</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>FULL EXPLORER</Text>
        <View style={{ width: 44 }} />
      </View>

      <View style={styles.placeholder}>
        <Text style={styles.emoji}>🗺️</Text>
        <Text style={styles.title}>Map Explorer</Text>
        <Text style={styles.subtitle}>
          This is a placeholder for the full-screen map explorer.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4], borderBottomWidth: 2, borderBottomColor: Colors.ink },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  placeholder: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing[6] },
  emoji: { fontSize: 64, marginBottom: Spacing[4] },
  title: { fontSize: 24, fontWeight: Typography.bold, color: Colors.ink, marginBottom: Spacing[2] },
  subtitle: { fontSize: 16, color: Colors.muted, textAlign: 'center' },
});
