import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView, KeyboardAvoidingView, Platform, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';

export default function ReportScreen() {
  const router = useRouter();
  const [desc, setDesc] = useState('');
  const [landmark, setLandmark] = useState('');
  const [photos, setPhotos] = useState<string[]>([]);
  
  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      alert('Sorry, we need camera permissions to make this work!');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!result.canceled && result.assets && result.assets.length > 0) {
      if (photos.length < 3) {
        setPhotos([...photos, result.assets[0].uri]);
      }
    }
  };

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      alert('Sorry, we need camera roll permissions to make this work!');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
      allowsMultipleSelection: true,
      selectionLimit: 3 - photos.length,
    });
    if (!result.canceled && result.assets && result.assets.length > 0) {
      const newUris = result.assets.map(a => a.uri);
      setPhotos([...photos, ...newUris].slice(0, 3));
    }
  };

  const removePhoto = (index: number) => {
    setPhotos(photos.filter((_, i) => i !== index));
  };
  
  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={styles.container}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
              <Text style={styles.backBtnText}>✕</Text>
            </TouchableOpacity>
            <Text style={styles.headerTitle}>C05 • REPORT</Text>
            <View style={{ width: 44 }} />
          </View>

          <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
            <View style={styles.titleSection}>
              <Text style={styles.mainTitle}>REPORT AN</Text>
              <View style={styles.issueBadgeContainer}>
                <View style={styles.issueBadgeShadow} />
                <View style={styles.issueBadge}>
                  <Text style={styles.issueText}>ISSUE</Text>
                </View>
              </View>
            </View>

            <View style={styles.offlineBanner}>
              <Text style={styles.offlineEmoji}>📶</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.offlineTitle}>You are offline</Text>
                <Text style={styles.offlineSub}>Reports will be queued and sent automatically.</Text>
              </View>
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>Photos ({photos.length}/3)</Text>
              
              {/* Image Previews */}
              {photos.length > 0 && (
                <View style={styles.photosGrid}>
                  {photos.map((uri, i) => (
                    <View key={i} style={styles.photoWrapper}>
                      <Image source={{ uri }} style={styles.photoImg} />
                      <TouchableOpacity style={styles.removeBtn} onPress={() => removePhoto(i)}>
                        <Text style={styles.removeBtnText}>✕</Text>
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              )}

              {photos.length < 3 && (
                <View style={styles.photoActionRow}>
                  <View style={styles.btnContainer}>
                    <View style={styles.btnShadow} />
                    <TouchableOpacity style={styles.btnFrame} onPress={takePhoto}>
                      <Text style={styles.btnIcon}>📷</Text>
                      <Text style={styles.btnLabel}>Camera</Text>
                    </TouchableOpacity>
                  </View>
                  <View style={styles.btnContainer}>
                    <View style={styles.btnShadow} />
                    <TouchableOpacity style={styles.btnFrame} onPress={pickImage}>
                      <Text style={styles.btnIcon}>🖼️</Text>
                      <Text style={styles.btnLabel}>Gallery</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>What's the issue?</Text>
              <View style={styles.inputContainer}>
                <View style={styles.inputShadow} />
                <TextInput
                  style={styles.textArea}
                  value={desc}
                  onChangeText={setDesc}
                  placeholder="Describe the problem..."
                  placeholderTextColor={Colors.muted}
                  multiline
                  textAlignVertical="top"
                />
              </View>
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>Voice note (optional)</Text>
              <View style={styles.audioBtnContainer}>
                <View style={styles.audioBtnShadow} />
                <TouchableOpacity style={styles.audioBtnFrame}>
                  <Text style={styles.audioBtnIcon}>🎙️</Text>
                  <Text style={styles.audioBtnLabel}>Record voice note</Text>
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.section}>
              <Text style={styles.label}>Location</Text>
              <View style={styles.inputContainer}>
                <View style={styles.inputShadow} />
                <TextInput
                  style={styles.input}
                  value={landmark}
                  onChangeText={setLandmark}
                  placeholder="Where is it?"
                  placeholderTextColor={Colors.muted}
                />
              </View>
              <View style={styles.locationHelp}>
                <Text style={styles.locationHelpText}>GPS unavailable while offline.</Text>
              </View>
            </View>
          </ScrollView>

          <View style={styles.footer}>
            <View style={styles.saveBtnContainer}>
              <View style={styles.saveBtnShadow} />
              <TouchableOpacity style={styles.saveBtnFrame} onPress={() => router.push('/(app)/(tabs)/my-cases')}>
                <Text style={styles.saveBtnLabel}>Save & Submit</Text>
                <View style={styles.saveBtnArrow}>
                  <Text style={styles.saveBtnArrowText}>→</Text>
                </View>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
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
  titleSection: { marginBottom: Spacing[6] },
  mainTitle: { fontSize: 42, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1 },
  issueBadgeContainer: { marginTop: -4, alignSelf: 'flex-start' },
  issueBadgeShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.sm },
  issueBadge: { backgroundColor: Colors.ink, paddingHorizontal: Spacing[3], paddingVertical: 2, borderRadius: Radii.sm, borderWidth: 2, borderColor: Colors.surface },
  issueText: { color: Colors.lime, fontSize: 28, fontWeight: Typography.black, letterSpacing: -0.5 },
  offlineBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.amber, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[3], marginBottom: Spacing[6] },
  offlineEmoji: { fontSize: 24, marginRight: Spacing[3] },
  offlineTitle: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink, marginBottom: 2 },
  offlineSub: { fontSize: 12, color: Colors.ink },
  section: { marginBottom: Spacing[5] },
  label: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink, marginBottom: Spacing[2] },
  
  photosGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing[3], marginBottom: Spacing[3] },
  photoWrapper: { position: 'relative', width: 90, height: 90 },
  photoImg: { width: '100%', height: '100%', borderRadius: Radii.md, borderWidth: 2, borderColor: Colors.ink },
  removeBtn: { position: 'absolute', top: -8, right: -8, width: 24, height: 24, borderRadius: 12, backgroundColor: Colors.fire, borderWidth: 1.5, borderColor: Colors.surface, alignItems: 'center', justifyContent: 'center' },
  removeBtnText: { color: Colors.surface, fontSize: 12, fontWeight: 'bold' },

  photoActionRow: { flexDirection: 'row', gap: Spacing[3] },
  btnContainer: { flex: 1 },
  btnShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  btnFrame: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, paddingVertical: Spacing[3], alignItems: 'center', justifyContent: 'center' },
  btnIcon: { fontSize: 24, marginBottom: Spacing[1] },
  btnLabel: { fontSize: 12, fontWeight: Typography.bold, color: Colors.ink },
  
  inputContainer: { width: '100%' },
  inputShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  textArea: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], fontSize: 16, color: Colors.ink, height: 120 },
  input: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], fontSize: 16, color: Colors.ink },
  audioBtnContainer: { width: '100%' },
  audioBtnShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  audioBtnFrame: { backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, padding: Spacing[4], flexDirection: 'row', alignItems: 'center', gap: Spacing[3] },
  audioBtnIcon: { fontSize: 24 },
  audioBtnLabel: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  locationHelp: { marginTop: Spacing[2] },
  locationHelpText: { fontSize: 12, color: Colors.muted },
  footer: { padding: Spacing[4], paddingBottom: Layout.bottomNavHeight, backgroundColor: Colors.ground, borderTopWidth: 2, borderTopColor: Colors.ink },
  saveBtnContainer: { width: '100%' },
  saveBtnShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  saveBtnFrame: { backgroundColor: Colors.lime, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, paddingVertical: Spacing[3], paddingHorizontal: Spacing[4], flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  saveBtnLabel: { fontSize: 18, fontWeight: Typography.bold, color: Colors.ink },
  saveBtnArrow: { width: 32, height: 32, borderRadius: 16, backgroundColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  saveBtnArrowText: { color: Colors.lime, fontSize: 18, fontWeight: Typography.bold },
});
