import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  Pressable,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
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
  PhotoTile,
  PlaceholderPhoto,
  HardShadow,
  StateView,
  useToast,
} from '../../../src/ui';
import { apiClient } from '../../../src/api/client';

const MAX_PHOTOS = 5;

export default function EvidenceScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { show } = useToast();
  const queryClient = useQueryClient();

  const [photos, setPhotos] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [uploading, setUploading] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.updateWorkOrder(id!, {
        note: note.trim() || undefined,
        photos: photos,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['workOrder', id], updated);
      queryClient.invalidateQueries({ queryKey: ['workOrders'] });
      show('Evidence saved', 'success');
      router.back();
    },
    onError: () => show('Failed to save evidence', 'error'),
  });

  const pickFromGallery = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Permission required',
        'Please allow access to your photo library in Settings.',
        [{ text: 'OK' }]
      );
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: MAX_PHOTOS - photos.length,
      quality: 0.8,
    });
    if (!result.canceled && result.assets.length > 0) {
      const compressed = await Promise.all(
        result.assets.map(async (asset) => {
          const manipulated = await ImageManipulator.manipulateAsync(
            asset.uri,
            [{ resize: { width: 1024 } }],
            { compress: 0.75, format: ImageManipulator.SaveFormat.JPEG }
          );
          return manipulated.uri;
        })
      );
      setPhotos((prev) => [...prev, ...compressed].slice(0, MAX_PHOTOS));
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Camera permission required',
        'Please allow camera access in Settings.',
        [{ text: 'OK' }]
      );
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      quality: 0.8,
      allowsEditing: false,
    });
    if (!result.canceled && result.assets[0]) {
      const manipulated = await ImageManipulator.manipulateAsync(
        result.assets[0].uri,
        [{ resize: { width: 1024 } }],
        { compress: 0.75, format: ImageManipulator.SaveFormat.JPEG }
      );
      setPhotos((prev) => [...prev, manipulated.uri].slice(0, MAX_PHOTOS));
    }
  };

  const removePhoto = (index: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    if (photos.length === 0 && !note.trim()) {
      show('Add at least one photo or note', 'warning');
      return;
    }
    mutation.mutate();
  };

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <PageHeader
          title="ADD EVIDENCE"
          eyebrow="F04 — EVIDENCE"
          onBack={() => router.back()}
        />

        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Photo capture actions */}
          <Text style={styles.sectionLabel}>PHOTOS</Text>
          <Text style={styles.hint}>
            Add up to {MAX_PHOTOS} photos. Tap to remove.
          </Text>

          <View style={styles.photoRow}>
            {photos.map((uri, index) => (
              <PhotoTile
                key={uri + index}
                uri={uri}
                size={100}
                onRemove={() => removePhoto(index)}
                style={styles.photoItem}
              />
            ))}
            {photos.length < MAX_PHOTOS ? (
              <PlaceholderPhoto
                size={100}
                onPress={takePhoto}
                style={styles.photoItem}
              />
            ) : null}
          </View>

          <View style={styles.captureButtons}>
            <HardShadow offset={{ dx: 2, dy: 2 }} radius={Radii.md} containerStyle={styles.captureHalf}>
              <Pressable
                style={styles.captureBtn}
                onPress={takePhoto}
                disabled={photos.length >= MAX_PHOTOS}
                accessibilityLabel="Take photo with camera"
              >
                <Ionicons name="camera-outline" size={20} color={Colors.ink} />
                <Text style={styles.captureBtnText}>CAMERA</Text>
              </Pressable>
            </HardShadow>

            <HardShadow offset={{ dx: 2, dy: 2 }} radius={Radii.md} containerStyle={styles.captureHalf}>
              <Pressable
                style={styles.captureBtn}
                onPress={pickFromGallery}
                disabled={photos.length >= MAX_PHOTOS}
                accessibilityLabel="Choose photos from gallery"
              >
                <Ionicons name="images-outline" size={20} color={Colors.ink} />
                <Text style={styles.captureBtnText}>GALLERY</Text>
              </Pressable>
            </HardShadow>
          </View>

          {/* Note */}
          <Field
            label="Note (optional)"
            hint="Describe what you observed"
            style={styles.fieldGap}
          >
            <Textarea
              value={note}
              onChangeText={setNote}
              placeholder="e.g. Pothole depth approx 15cm, approx 1m diameter..."
              numberOfLines={4}
            />
          </Field>

          {/* Photo count indicator */}
          {photos.length > 0 ? (
            <View style={styles.countRow}>
              <Ionicons name="images" size={14} color={Colors.wine} />
              <Text style={styles.countText}>
                {photos.length} / {MAX_PHOTOS} photos attached
              </Text>
            </View>
          ) : null}

          <Button
            title={mutation.isPending ? 'Saving...' : 'SAVE EVIDENCE'}
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
  sectionLabel: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.muted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  hint: {
    fontFamily: FontFamily.sans,
    fontSize: 13,
    color: Colors.muted,
    marginBottom: 8,
  },
  photoRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 4,
  },
  photoItem: {
    marginBottom: 0,
  },
  captureButtons: {
    flexDirection: 'row',
    gap: 10,
  },
  captureHalf: {
    flex: 1,
  },
  captureBtn: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.md,
    borderWidth: 2,
    borderColor: Colors.ink,
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  captureBtnText: {
    fontFamily: FontFamily.mono,
    fontSize: 12,
    fontWeight: '500',
    color: Colors.ink,
    letterSpacing: 1,
  },
  fieldGap: { marginBottom: 4 },
  countRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  countText: {
    fontFamily: FontFamily.mono,
    fontSize: 12,
    color: Colors.wine,
    fontWeight: '500',
  },
  cancelBtn: { marginTop: 4 },
});
