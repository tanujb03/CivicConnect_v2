import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  Image,
  Platform,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Colors, Typography, Spacing, Radii, Shadows } from '../constants/theme';

interface CameraCaptureModalProps {
  visible: boolean;
  onClose: () => void;
  onCapture: (uri: string) => void;
}

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

export default function CameraCaptureModal({
  visible,
  onClose,
  onCapture,
}: CameraCaptureModalProps) {
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [flashEffect, setFlashEffect] = useState(false);

  const videoRef = useRef<any>(null);
  const streamRef = useRef<any>(null);

  // Initialize or teardown camera stream on web
  useEffect(() => {
    if (!visible) {
      stopCamera();
      setCapturedUri(null);
      setError(null);
      return;
    }

    if (Platform.OS === 'web') {
      startWebCamera();
    } else {
      // Native mobile launch
      launchNativeCamera();
    }

    return () => {
      stopCamera();
    };
  }, [visible, facingMode]);

  async function launchNativeCamera() {
    setLoading(true);
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        setError('Camera permission denied in system settings.');
        setLoading(false);
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        quality: 0.85,
        allowsEditing: true,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        onCapture(result.assets[0].uri);
        onClose();
      } else {
        onClose();
      }
    } catch (e: any) {
      setError(e?.message || 'Could not open native camera');
    } finally {
      setLoading(false);
    }
  }

  async function startWebCamera() {
    stopCamera();
    setLoading(true);
    setError(null);

    const nav = typeof navigator !== 'undefined' ? navigator : null;
    if (!nav?.mediaDevices?.getUserMedia) {
      setError('Live camera preview is not supported by this browser. Use gallery or file capture instead.');
      setLoading(false);
      return;
    }

    try {
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      };

      const stream = await nav.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      // Attach stream to HTML video element
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
      }
      setCameraActive(true);
    } catch (err: any) {
      console.warn('Camera access error:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('Camera permission blocked. Please allow camera access in your browser address bar.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setError('No camera hardware found on this device.');
      } else {
        setError(`Unable to access camera: ${err.message || 'Unknown error'}`);
      }
    } finally {
      setLoading(false);
    }
  }

  function stopCamera() {
    if (streamRef.current) {
      try {
        const tracks = streamRef.current.getTracks();
        tracks.forEach((track: any) => track.stop());
      } catch {}
      streamRef.current = null;
    }
    setCameraActive(false);
  }

  function toggleCameraFacing() {
    setFacingMode((prev) => (prev === 'environment' ? 'user' : 'environment'));
  }

  function takeSnapshot() {
    if (!videoRef.current) return;

    setFlashEffect(true);
    setTimeout(() => setFlashEffect(false), 200);

    try {
      const video = videoRef.current;
      const width = video.videoWidth || 640;
      const height = video.videoHeight || 480;

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext('2d');
      if (ctx) {
        // If front camera, mirror image for natural feel
        if (facingMode === 'user') {
          ctx.translate(width, 0);
          ctx.scale(-1, 1);
        }
        ctx.drawImage(video, 0, 0, width, height);

        const dataUrl = canvas.toDataURL('image/jpeg', 0.88);
        setCapturedUri(dataUrl);
      }
    } catch (e: any) {
      console.warn('Snapshot error:', e);
      setError('Could not capture frame from camera.');
    }
  }

  function handleConfirmPhoto() {
    if (capturedUri) {
      onCapture(capturedUri);
      stopCamera();
      onClose();
    }
  }

  function handleRetake() {
    setCapturedUri(null);
    if (Platform.OS === 'web') {
      startWebCamera();
    }
  }

  function handleFallbackFilePick() {
    if (typeof document !== 'undefined') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.capture = 'environment';
      input.onchange = (e: any) => {
        const file = e.target?.files?.[0];
        if (file) {
          const uri = URL.createObjectURL(file);
          onCapture(uri);
          stopCamera();
          onClose();
        }
      };
      input.click();
    }
  }

  if (!visible) return null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.modalBox}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerBadge}>
              <View style={[styles.statusDot, cameraActive && styles.statusDotActive]} />
              <Text style={styles.headerTitle}>
                {capturedUri ? 'Review Photo' : 'Device Camera'}
              </Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityRole="button">
              <Text style={styles.closeBtnText}>✕</Text>
            </TouchableOpacity>
          </View>

          {/* Camera Viewport / Captured Preview */}
          <View style={styles.viewportContainer}>
            {loading && (
              <View style={styles.centerMessage}>
                <ActivityIndicator size="large" color="#fff" />
                <Text style={styles.messageText}>Connecting to camera hardware…</Text>
              </View>
            )}

            {error ? (
              <View style={styles.centerMessage}>
                <Text style={styles.errorEmoji}>📷</Text>
                <Text style={styles.errorTitle}>Camera Not Available</Text>
                <Text style={styles.errorSub}>{error}</Text>
                <TouchableOpacity
                  style={styles.fallbackBtn}
                  onPress={handleFallbackFilePick}
                  accessibilityRole="button"
                >
                  <Text style={styles.fallbackBtnText}>📁 Upload Photo from Device</Text>
                </TouchableOpacity>
              </View>
            ) : capturedUri ? (
              <View style={styles.previewBox}>
                <Image source={{ uri: capturedUri }} style={styles.previewImage} resizeMode="cover" />
                <View style={styles.reticleBadge}>
                  <Text style={styles.reticleBadgeText}>✓ Ready to attach</Text>
                </View>
              </View>
            ) : (
              <View style={styles.videoWrapper}>
                {Platform.OS === 'web' && (
                  <video
                    ref={(el) => {
                      videoRef.current = el;
                      if (el && streamRef.current && !el.srcObject) {
                        el.srcObject = streamRef.current;
                        el.play().catch(() => {});
                      }
                    }}
                    autoPlay
                    playsInline
                    muted
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      transform: facingMode === 'user' ? 'scaleX(-1)' : 'none',
                    }}
                  />
                )}

                {/* Framing guides */}
                <View style={styles.crosshairCornerTL} />
                <View style={styles.crosshairCornerTR} />
                <View style={styles.crosshairCornerBL} />
                <View style={styles.crosshairCornerBR} />

                {/* Flash effect overlay */}
                {flashEffect && <View style={styles.flashOverlay} />}
              </View>
            )}
          </View>

          {/* Controls Footer */}
          <View style={styles.footer}>
            {capturedUri ? (
              <View style={styles.previewActions}>
                <TouchableOpacity
                  style={styles.retakeBtn}
                  onPress={handleRetake}
                  accessibilityRole="button"
                >
                  <Text style={styles.retakeBtnText}>↺ Retake</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.usePhotoBtn}
                  onPress={handleConfirmPhoto}
                  accessibilityRole="button"
                >
                  <Text style={styles.usePhotoBtnText}>Use Photo ✓</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View style={styles.captureControls}>
                {/* Switch camera button */}
                <TouchableOpacity
                  style={styles.switchCamBtn}
                  onPress={toggleCameraFacing}
                  disabled={!cameraActive}
                  accessibilityLabel="Switch Camera"
                >
                  <Text style={styles.switchCamIcon}>🔄</Text>
                </TouchableOpacity>

                {/* Big round Shutter button */}
                <TouchableOpacity
                  style={[styles.shutterBtnOuter, !cameraActive && styles.shutterBtnDisabled]}
                  onPress={takeSnapshot}
                  disabled={!cameraActive}
                  accessibilityLabel="Take Photo"
                  accessibilityRole="button"
                >
                  <View style={styles.shutterBtnInner} />
                </TouchableOpacity>

                {/* Gallery fallback */}
                <TouchableOpacity
                  style={styles.galleryShortcutBtn}
                  onPress={handleFallbackFilePick}
                  accessibilityLabel="Choose from device"
                >
                  <Text style={styles.galleryShortcutIcon}>🖼️</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing[4],
  },
  modalBox: {
    width: '100%',
    maxWidth: 440,
    backgroundColor: '#0F172A',
    borderRadius: Radii['2xl'],
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    ...Shadows.lg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing[4],
    paddingVertical: Spacing[3],
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  headerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[2],
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#94A3B8',
  },
  statusDotActive: {
    backgroundColor: '#10B981',
  },
  headerTitle: {
    color: '#F8FAFC',
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
    letterSpacing: 0.2,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeBtnText: {
    color: '#CBD5E1',
    fontSize: 16,
    fontWeight: 'bold',
  },
  viewportContainer: {
    width: '100%',
    height: 360,
    backgroundColor: '#020617',
    position: 'relative',
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
  },
  videoWrapper: {
    width: '100%',
    height: '100%',
    position: 'relative',
  },
  flashOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#FFFFFF',
    opacity: 0.8,
  },
  previewBox: {
    width: '100%',
    height: '100%',
    position: 'relative',
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
  reticleBadge: {
    position: 'absolute',
    bottom: Spacing[3],
    alignSelf: 'center',
    backgroundColor: 'rgba(16, 185, 129, 0.9)',
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1],
    borderRadius: Radii.full,
  },
  reticleBadgeText: {
    color: '#fff',
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
  },
  crosshairCornerTL: {
    position: 'absolute',
    top: 24,
    left: 24,
    width: 28,
    height: 28,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderColor: 'rgba(255, 255, 255, 0.7)',
    borderRadius: 4,
  },
  crosshairCornerTR: {
    position: 'absolute',
    top: 24,
    right: 24,
    width: 28,
    height: 28,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderColor: 'rgba(255, 255, 255, 0.7)',
    borderRadius: 4,
  },
  crosshairCornerBL: {
    position: 'absolute',
    bottom: 24,
    left: 24,
    width: 28,
    height: 28,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderColor: 'rgba(255, 255, 255, 0.7)',
    borderRadius: 4,
  },
  crosshairCornerBR: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 28,
    height: 28,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderColor: 'rgba(255, 255, 255, 0.7)',
    borderRadius: 4,
  },
  centerMessage: {
    alignItems: 'center',
    paddingHorizontal: Spacing[6],
    gap: Spacing[2],
  },
  messageText: {
    color: '#E2E8F0',
    fontSize: Typography.sm,
    marginTop: Spacing[2],
  },
  errorEmoji: {
    fontSize: 40,
    marginBottom: Spacing[2],
  },
  errorTitle: {
    color: '#F87171',
    fontSize: Typography.base,
    fontWeight: Typography.bold,
  },
  errorSub: {
    color: '#94A3B8',
    fontSize: Typography.xs,
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: Spacing[3],
  },
  fallbackBtn: {
    backgroundColor: Colors.brand[600],
    paddingHorizontal: Spacing[4],
    paddingVertical: Spacing[2.5],
    borderRadius: Radii.lg,
  },
  fallbackBtnText: {
    color: '#fff',
    fontSize: Typography.sm,
    fontWeight: Typography.semibold,
  },
  footer: {
    paddingHorizontal: Spacing[5],
    paddingVertical: Spacing[4],
    backgroundColor: '#0F172A',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  captureControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
  },
  switchCamBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  switchCamIcon: {
    fontSize: 20,
  },
  shutterBtnOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    borderColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
  },
  shutterBtnDisabled: {
    opacity: 0.4,
  },
  shutterBtnInner: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#FFFFFF',
  },
  galleryShortcutBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  galleryShortcutIcon: {
    fontSize: 20,
  },
  previewActions: {
    flexDirection: 'row',
    gap: Spacing[3],
  },
  retakeBtn: {
    flex: 1,
    paddingVertical: Spacing[3.5],
    borderRadius: Radii.xl,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  retakeBtnText: {
    color: '#E2E8F0',
    fontSize: Typography.base,
    fontWeight: Typography.semibold,
  },
  usePhotoBtn: {
    flex: 1.5,
    paddingVertical: Spacing[3.5],
    borderRadius: Radii.xl,
    backgroundColor: Colors.brand[600],
    alignItems: 'center',
    ...Shadows.civic,
  },
  usePhotoBtnText: {
    color: '#FFFFFF',
    fontSize: Typography.base,
    fontWeight: Typography.bold,
  },
});
