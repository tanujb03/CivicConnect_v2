import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Dimensions, ActivityIndicator } from 'react-native';
import { Colors, Typography, Spacing, Radii, Shadows } from '../constants/theme';

interface TransitionScreenProps {
  onComplete?: () => void;
  role?: 'citizen' | 'field_worker';
}

const CITIZEN_MESSAGES = [
  '🕳️ 50 potholes fixed this week',
  '🚮 Your city is 10kg free of garbage',
  '💡 80% success rate in electricity issues',
];

const FIELD_WORKER_MESSAGES = [
  '📋 Syncing your work orders…',
  '📍 Loading your assigned zones…',
  '🔧 Ready for field operations',
];

export default function TransitionScreen({ onComplete, role = 'citizen' }: TransitionScreenProps) {
  const MESSAGES = role === 'field_worker' ? FIELD_WORKER_MESSAGES : CITIZEN_MESSAGES;
  const [currentMessage, setCurrentMessage] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentMessage((prev) => {
        if (prev < MESSAGES.length - 1) {
          return prev + 1;
        } else {
          clearInterval(timer);
          if (onComplete) setTimeout(onComplete, 800);
          return prev;
        }
      });
    }, 1200);

    return () => clearInterval(timer);
  }, [onComplete, MESSAGES.length]);

  return (
    <View style={styles.container}>
      {/* Background Orbs */}
      <View style={[styles.orb, styles.orb1]} />
      <View style={[styles.orb, styles.orb2]} />

      {/* Logo + Title */}
      <View style={styles.logoRow}>
        <View style={styles.logoBox}>
          <Text style={styles.logoEmoji}>🏙️</Text>
        </View>
        <Text style={styles.logoTitle}>CivicConnect</Text>
      </View>

      {/* Message content */}
      <View style={styles.messageBox}>
        <Text style={styles.messageText}>{MESSAGES[currentMessage]}</Text>
      </View>

      {/* Loading indicator */}
      <ActivityIndicator size="small" color="rgba(255,255,255,0.7)" style={styles.spinner} />

      {/* Progress capsules */}
      <View style={styles.dotsRow}>
        {MESSAGES.map((_, i) => (
          <View
            key={i}
            style={[
              styles.dot,
              i === currentMessage ? styles.dotActive : i < currentMessage ? styles.dotCompleted : styles.dotInactive,
            ]}
          />
        ))}
      </View>

      {/* Tap to enter dashboard immediately */}
      {onComplete && (
        <TouchableOpacity
          style={styles.skipBtn}
          onPress={onComplete}
          accessibilityRole="button"
          accessibilityLabel="Continue to Dashboard"
        >
          <Text style={styles.skipBtnText}>Continue to Dashboard →</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const { width, height } = Dimensions.get('window');

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d4a1a',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing[6],
  },
  orb: {
    position: 'absolute',
    borderRadius: 999,
    opacity: 0.25,
  },
  orb1: {
    top: height * 0.1,
    left: -40,
    width: 220,
    height: 220,
    backgroundColor: '#27a94a',
  },
  orb2: {
    bottom: height * 0.15,
    right: -40,
    width: 260,
    height: 260,
    backgroundColor: '#6cc77a',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3],
    marginBottom: Spacing[10],
  },
  logoBox: {
    width: 48,
    height: 48,
    borderRadius: Radii.lg,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
  },
  logoEmoji: { fontSize: 26 },
  logoTitle: {
    color: '#fff',
    fontSize: Typography.xl,
    fontWeight: Typography.extrabold,
    letterSpacing: -0.5,
  },
  messageBox: {
    paddingHorizontal: Spacing[6],
    paddingVertical: Spacing[8],
    borderRadius: Radii['2xl'],
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    maxWidth: 360,
    marginBottom: Spacing[6],
  },
  messageText: {
    fontSize: 22,
    fontWeight: Typography.bold,
    color: '#ffffff',
    textAlign: 'center',
    lineHeight: 32,
  },
  spinner: {
    marginBottom: Spacing[8],
  },
  dotsRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  dot: {
    height: 6,
    borderRadius: 3,
  },
  dotActive: {
    width: 24,
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
  },
  dotCompleted: {
    width: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.6)',
  },
  dotInactive: {
    width: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
  },
  skipBtn: {
    marginTop: Spacing[8],
    paddingHorizontal: Spacing[6],
    paddingVertical: Spacing[3],
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    borderRadius: Radii.full,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.25)',
  },
  skipBtnText: {
    color: '#ffffff',
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
  },
});

