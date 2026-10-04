/**
 * F04 — Resolution Evidence
 *
 * Mandatory evidence capture for field work:
 * - After-repair photographs (camera / gallery)
 * - Optional video / inspection clip
 * - Work note describing technical fix
 * - Materials and parts inventory consumed
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Image,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import {
  Colors,
  Typography,
  Spacing,
  Radii,
  Shadows,
} from '../../../src/constants/theme';
import { workOrdersApi } from '../../../src/api/client';
import type { WorkOrder } from '../../../src/types';

export default function ResolutionEvidenceScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form State
  const [photos, setPhotos] = useState<string[]>([]);
  const [workNote, setWorkNote] = useState('');
  const [materialsUsed, setMaterialsUsed] = useState('');

  useEffect(() => {
    (async () => {
      if (!id) return;
      try {
        const data = await workOrdersApi.get(id);
        if (data) {
          setOrder(data);
          if (data.work_note) setWorkNote(data.work_note);
          if (data.materials_used) setMaterialsUsed(data.materials_used);
        }
      } catch {}
      finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const handleCapturePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Camera Permission', 'Camera permission is required to capture resolution evidence photos.');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      setPhotos(prev => [...prev, result.assets[0].uri]);
    }
  };

  const handlePickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets) {
      const uris = result.assets.map(a => a.uri);
      setPhotos(prev => [...prev, ...uris]);
    }
  };

  const handleRemovePhoto = (index: number) => {
    setPhotos(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmitEvidence = async () => {
    if (!order) return;
    if (photos.length === 0) {
      Alert.alert('Photo Required', 'At least one "After Repair" photograph is mandatory for municipal verification.');
      return;
    }
    if (!workNote.trim()) {
      Alert.alert('Work Note Required', 'Please enter a brief note describing the repair work completed.');
      return;
    }

    setSubmitting(true);
    try {
      await workOrdersApi.uploadEvidence(order.id, photos, workNote, materialsUsed);
      Alert.alert('Evidence Saved', 'Resolution photos and notes have been registered for this work order.', [
        {
          text: 'Proceed to Complete Work',
          onPress: () => router.push(`/work-order/complete/${order.id}`),
        },
      ]);
    } catch {
      Alert.alert('Error', 'Failed to save evidence. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !order) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.action[600]} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={styles.backBtnText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Resolution Evidence</Text>
        <View style={{ width: 50 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Case Strip */}
        <View style={styles.orderStrip}>
          <Text style={styles.caseNumber}>{order.case_number}</Text>
          <Text style={styles.orderTitle}>{order.title}</Text>
        </View>

        {/* Photo Upload Section */}
        <View style={styles.card}>
          <View style={styles.cardTitleRow}>
            <Text style={styles.cardTitle}>1. After-Repair Photos (Mandatory)</Text>
            <Text style={styles.photoCountText}>{photos.length} attached</Text>
          </View>
          <Text style={styles.cardDesc}>
            Take clear photos of the fixed site. These photos will be presented to citizens and ward supervisors for verification.
          </Text>

          {/* Action Buttons */}
          <View style={styles.photoButtonsRow}>
            <TouchableOpacity style={styles.cameraBtn} onPress={handleCapturePhoto}>
              <Text style={styles.cameraBtnIcon}>📷</Text>
              <Text style={styles.cameraBtnText}>Take Live Photo</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.galleryBtn} onPress={handlePickFromGallery}>
              <Text style={styles.galleryBtnIcon}>🖼️</Text>
              <Text style={styles.galleryBtnText}>Select Photos</Text>
            </TouchableOpacity>
          </View>

          {/* Photos Grid */}
          {photos.length > 0 && (
            <View style={styles.photoGrid}>
              {photos.map((uri, idx) => (
                <View key={idx} style={styles.photoThumbWrap}>
                  <Image source={{ uri }} style={styles.photoThumb} />
                  <TouchableOpacity
                    style={styles.deletePhotoBtn}
                    onPress={() => handleRemovePhoto(idx)}
                  >
                    <Text style={styles.deletePhotoText}>✕</Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* Work Note */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>2. Work & Repair Notes</Text>
          <Text style={styles.cardDesc}>
            Explain the root cause and the specific corrective work undertaken by the crew.
          </Text>
          <TextInput
            style={styles.textArea}
            multiline
            numberOfLines={4}
            placeholder="e.g., Excavated 1.2m, sealed broken coupling with heavy-duty sleeve, backfilled and compacted asphalt."
            placeholderTextColor={Colors.neutral[400]}
            value={workNote}
            onChangeText={setWorkNote}
          />
        </View>

        {/* Materials & Parts Consumed */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>3. Materials & Equipment Consumed</Text>
          <Text style={styles.cardDesc}>
            Log supplies used from municipal inventory for audit and restocking.
          </Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 2 bags cold bitumen mix, 1x 4-inch PVC joint, 4 bolts"
            placeholderTextColor={Colors.neutral[400]}
            value={materialsUsed}
            onChangeText={setMaterialsUsed}
          />
        </View>
      </ScrollView>

      {/* Submit / Proceed Button */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={[styles.submitBtn, photos.length === 0 && styles.submitBtnDisabled]}
          onPress={handleSubmitEvidence}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.submitBtnText}>
              Save Evidence & Proceed to Completion (F05) →
            </Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.neutral[200],
  },
  backBtn: {
    padding: Spacing.sm,
  },
  backBtnText: {
    fontSize: Typography.bodyLarge.fontSize,
    color: Colors.action[700],
    fontWeight: '700',
  },
  headerTitle: {
    fontSize: Typography.titleMedium.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  scrollContent: {
    padding: Spacing.md,
    gap: Spacing.md,
    paddingBottom: 110,
  },
  orderStrip: {
    backgroundColor: '#FFFFFF',
    padding: Spacing.md,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: 2,
    ...Shadows.sm,
  },
  caseNumber: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '800',
    color: Colors.action[700],
  },
  orderTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  card: {
    backgroundColor: '#FFFFFF',
    padding: Spacing.lg,
    borderRadius: Radii.lg,
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    gap: Spacing.sm,
    ...Shadows.sm,
  },
  cardTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: Typography.titleSmall.fontSize,
    fontWeight: '700',
    color: Colors.neutral[900],
  },
  photoCountText: {
    fontSize: Typography.labelSmall.fontSize,
    fontWeight: '700',
    color: Colors.action[700],
  },
  cardDesc: {
    fontSize: Typography.bodySmall.fontSize,
    color: Colors.neutral[500],
    lineHeight: 18,
  },
  photoButtonsRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.xs,
  },
  cameraBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.action[600],
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    gap: Spacing.xs,
  },
  cameraBtnIcon: {
    fontSize: 18,
  },
  cameraBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: Typography.labelMedium.fontSize,
  },
  galleryBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.neutral[100],
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    gap: Spacing.xs,
  },
  galleryBtnIcon: {
    fontSize: 18,
  },
  galleryBtnText: {
    color: Colors.neutral[700],
    fontWeight: '700',
    fontSize: Typography.labelMedium.fontSize,
  },
  photoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  photoThumbWrap: {
    width: 90,
    height: 90,
    borderRadius: Radii.md,
    overflow: 'hidden',
    position: 'relative',
  },
  photoThumb: {
    width: '100%',
    height: '100%',
  },
  deletePhotoBtn: {
    position: 'absolute',
    top: 4,
    right: 4,
    backgroundColor: '#000000CC',
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  deletePhotoText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800',
  },
  textArea: {
    backgroundColor: Colors.neutral[50],
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    borderRadius: Radii.md,
    padding: Spacing.md,
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[900],
    minHeight: 90,
    textAlignVertical: 'top',
  },
  input: {
    backgroundColor: Colors.neutral[50],
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    borderRadius: Radii.md,
    padding: Spacing.md,
    fontSize: Typography.bodyMedium.fontSize,
    color: Colors.neutral[900],
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[200],
    ...Shadows.md,
  },
  submitBtn: {
    backgroundColor: '#0284C7',
    paddingVertical: Spacing.md,
    borderRadius: Radii.md,
    alignItems: 'center',
  },
  submitBtnDisabled: {
    backgroundColor: Colors.neutral[300],
  },
  submitBtnText: {
    fontSize: Typography.labelLarge.fontSize,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
