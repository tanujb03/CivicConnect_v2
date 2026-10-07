import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radii, Shadows, Spacing } from '../../../src/theme/tokens';
import { FontFamily } from '../../../src/theme/fonts';
import {
  PageHeader,
  Field,
  Textarea,
  Button,
  Card,
  PhotoTile,
  PlaceholderPhoto,
  HardShadow,
  StateView,
  useToast,
} from '../../../src/ui';
import { apiClient } from '../../../src/api/client';

export default function CompleteScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { show } = useToast();
  const queryClient = useQueryClient();

  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState('');
  const [photos, setPhotos] = useState<string[]>([]);

  const { data: workOrder, isLoading } = useQuery({
    queryKey: ['workOrder', id],
    queryFn: () => apiClient.getWorkOrder(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.updateWorkOrder(id!, {
        status: 'DONE',
        note: note.trim(),
        photos: photos,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['workOrder', id], updated);
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      queryClient.invalidateQueries({ queryKey: ['kpi'] });
      show('Work order completed!', 'success');
      // Navigate back to the list
      router.push('/(tabs)/' as any);
    },
    onError: () => show('Failed to complete work order', 'error'),
  });

  const handleSubmit = () => {
    if (!note.trim()) {
      setNoteError('Resolution note is required to close this work order');
      return;
    }
    setNoteError('');
    Alert.alert(
      'Mark as Resolved?',
      'This will close the work order and notify the citizen. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mark Resolved',
          onPress: () => mutation.mutate(),
        },
      ]
    );
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Camera permission required', 'Please allow camera access in Settings.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (!result.canceled && result.assets[0]) {
      const m = await ImageManipulator.manipulateAsync(
        result.assets[0].uri,
        [{ resize: { width: 1024 } }],
        { compress: 0.75, format: ImageManipulator.SaveFormat.JPEG }
      );
      setPhotos((prev) => [...prev, m.uri].slice(0, 5));
    }
  };

  const pickFromGallery = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission required', 'Please allow photo library access in Settings.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: 5 - photos.length,
      quality: 0.8,
    });
    if (!result.canceled) {
      const compressed = await Promise.all(
        result.assets.map(async (a) => {
          const m = await ImageManipulator.manipulateAsync(
            a.uri,
            [{ resize: { width: 1024 } }],
            { compress: 0.75, format: ImageManipulator.SaveFormat.JPEG }
          );
          return m.uri;
        })
      );
      setPhotos((prev) => [...prev, ...compressed].slice(0, 5));
    }
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root}>
        <StateView variant="loading" title="Loading..." />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <PageHeader
          title="COMPLETE WORK"
          eyebrow="F05 — RESOLVE"
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Work order info */}
          {workOrder ? (
            <Card shadow="hard" containerStyle={styles.infoCard}>
              <Text style={styles.woTitle}>{workOrder.title}</Text>
              <Text style={styles.woAddress}>{workOrder.address}</Text>
            </Card>
          ) : null}

          {/* Confirm banner */}
          <HardShadow offset={{ dx: 3, dy: 3 }} radius={Radii.lg} containerStyle={styles.confirmBanner}>
            <View style={styles.confirmBannerInner}>
              <Ionicons name="checkmark-circle" size={24} color={Colors.lime} />
              <Text style={styles.confirmText}>
                Completing this work order will notify the citizen and supervisor.
              </Text>
            </View>
          </HardShadow>

          {/* Resolution note */}
          <Field
            label="Resolution Note"
            error={noteError}
            required
            hint="Describe the work done and any follow-up required"
            style={styles.fieldGap}
          >
            <Textarea
              value={note}
              onChangeText={(t) => {
                setNote(t);
                if (noteError) setNoteError('');
              }}
              placeholder="e.g. Pothole filled with hot mix asphalt and compacted. Road surface levelled. Area cleaned."
              numberOfLines={5}
              hasError={!!noteError}
            />
          </Field>

          {/* After photos */}
          <Text style={styles.sectionLabel}>AFTER PHOTOS (recommended)</Text>
          <View style={styles.photoRow}>
            {photos.map((uri, index) => (
              <PhotoTile
                key={uri + index}
                uri={uri}
                size={100}
                onRemove={() => setPhotos((prev) => prev.filter((_, i) => i !== index))}
                style={styles.photoItem}
              />
            ))}
            {photos.length < 5 ? (
              <PlaceholderPhoto size={100} onPress={takePhoto} style={styles.photoItem} />
            ) : null}
          </View>

          <View style={styles.captureButtons}>
            <HardShadow offset={{ dx: 2, dy: 2 }} radius={Radii.md} containerStyle={styles.captureHalf}>
              <Pressable style={styles.captureBtn} onPress={takePhoto}>
                <Ionicons name="camera-outline" size={18} color={Colors.ink} />
                <Text style={styles.captureBtnText}>CAMERA</Text>
              </Pressable>
            </HardShadow>
            <HardShadow offset={{ dx: 2, dy: 2 }} radius={Radii.md} containerStyle={styles.captureHalf}>
              <Pressable style={styles.captureBtn} onPress={pickFromGallery}>
                <Ionicons name="images-outline" size={18} color={Colors.ink} />
                <Text style={styles.captureBtnText}>GALLERY</Text>
              </Pressable>
            </HardShadow>
          </View>

          {/* Submit */}
          <Button
            title={mutation.isPending ? 'Completing...' : 'MARK AS RESOLVED'}
            onPress={handleSubmit}
            variant="wine"
            loading={mutation.isPending}
          />

          <Button
            title="CANCEL"
            onPress={() => router.back()}
            variant="ghost"
            style={styles.cancelBtn}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.ground },
  flex: { flex: 1 },
  content: {
    paddingHorizontal: Spacing.screenH,
    paddingBottom: 48,
    gap: 16,
  },
  infoCard: { width: undefined, marginBottom: 0 },
  woTitle: {
    fontFamily: FontFamily.sansSemiBold,
    fontSize: 16,
    color: Colors.ink,
    marginBottom: 4,
    lineHeight: 22,
  },
  woAddress: {
    fontFamily: FontFamily.sans,
    fontSize: 13,
    color: Colors.muted,
  },
  confirmBanner: { width: '100%' },
  confirmBannerInner: {
    backgroundColor: Colors.wine,
    borderRadius: Radii.lg,
    borderWidth: 2,
    borderColor: Colors.ink,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  confirmText: {
    fontFamily: FontFamily.sans,
    fontSize: 14,
    color: Colors.onWine,
    lineHeight: 20,
    flex: 1,
  },
  fieldGap: { marginBottom: 4 },
  sectionLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
  photoRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  photoItem: { marginBottom: 0 },
  captureButtons: { flexDirection: 'row', gap: 10 },
  captureHalf: { flex: 1 },
  captureBtn: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    height: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  captureBtnText: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    fontWeight: '500',
    color: Colors.ink,
    letterSpacing: 1,
  },
  cancelBtn: { marginTop: 4 },
});
