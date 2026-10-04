/**
 * C02 — Authentication (Login)
 *
 * Phone/email input → OTP → verify
 * Supports both phone and email flows.
 */

import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Shadows } from '../../src/constants/theme';
import { useAuthContext } from '../../src/context/AuthContext';
import { StatusBar } from 'expo-status-bar';
import TransitionScreen from '../../src/components/TransitionScreen';

type LoginStep = 'input' | 'otp' | 'loading';
type InputMode = 'phone' | 'email';

export default function LoginScreen() {
  const router = useRouter();
  const { requestOtp, verifyOtp, demoLogin } = useAuthContext();

  const [step, setStep] = useState<LoginStep>('input');
  const [inputMode, setInputMode] = useState<InputMode>('phone');
  const [selectedRole, setSelectedRole] = useState<'citizen' | 'field_worker'>('citizen');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState<string | null>(null);
  const [showTransition, setShowTransition] = useState(false);

  const otpRefs = useRef<(TextInput | null)[]>([]);

  const inputValue = inputMode === 'phone' ? phone : email;
  const isInputValid = inputMode === 'phone'
    ? /^\+?[0-9]{10,15}$/.test(phone.replace(/\s/g, ''))
    : /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  async function handleSendOtp() {
    if (!isInputValid) return;
    setError(null);
    setStep('loading');
    try {
      await requestOtp(
        inputMode === 'phone' ? { phone: phone.trim() } : { email: email.trim() }
      );
      setStep('otp');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send OTP. Please try again.');
      setStep('input');
    }
  }

  function handleOtpChange(value: string, index: number) {
    const next = [...otp];
    next[index] = value;
    setOtp(next);
    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  }

  function handleOtpKeyPress(key: string, index: number) {
    if (key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  }

  async function handleVerifyOtp() {
    const code = otp.join('');
    if (code.length < 6) return;
    setError(null);
    setStep('loading');
    try {
      await verifyOtp(
        inputMode === 'phone'
          ? { phone: phone.trim(), otp: code }
          : { email: email.trim(), otp: code }
      );
      // Show transition screen briefly; navigation happens via auth guard in _layout.tsx
      setShowTransition(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid OTP. Please try again.');
      setStep('otp');
      setOtp(['', '', '', '', '', '']);
      otpRefs.current[0]?.focus();
    }
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <StatusBar style="light" />

      {/* Transition overlay — shown after successful login */}
      <Modal visible={showTransition} transparent animationType="fade">
        <TransitionScreen
          role={selectedRole}
          onComplete={() => {
            setShowTransition(false);
            router.replace('/(app)/(tabs)/dashboard');
          }}
        />
      </Modal>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity
            onPress={() => {
              if (step === 'otp') { setStep('input'); setOtp(['','','','','','']); }
              else router.back();
            }}
            style={styles.backButton}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <View style={styles.logoBox}>
            <Text style={styles.logoEmoji}>🏙️</Text>
          </View>
          <Text style={styles.headerTitle}>CivicConnect</Text>
        </View>

        <View style={styles.body}>
          {step === 'loading' ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={Colors.brand[500]} />
              <Text style={styles.loadingText}>Please wait…</Text>
            </View>
          ) : step === 'input' ? (
            <>
              <Text style={styles.title}>Sign in to continue</Text>
              <Text style={styles.subtitle}>
                Enter your phone number or email. We'll send you a one-time code.
              </Text>

              {/* Mode toggle */}
              <View style={styles.modeToggle}>
                <TouchableOpacity
                  style={[styles.modeTab, inputMode === 'phone' && styles.modeTabActive]}
                  onPress={() => setInputMode('phone')}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: inputMode === 'phone' }}
                >
                  <Text style={[styles.modeTabText, inputMode === 'phone' && styles.modeTabTextActive]}>
                    📱 Phone
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.modeTab, inputMode === 'email' && styles.modeTabActive]}
                  onPress={() => setInputMode('email')}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: inputMode === 'email' }}
                >
                  <Text style={[styles.modeTabText, inputMode === 'email' && styles.modeTabTextActive]}>
                    ✉️ Email
                  </Text>
                </TouchableOpacity>
              </View>

              {inputMode === 'phone' ? (
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputPrefix}>+91</Text>
                  <TextInput
                    style={styles.textInput}
                    value={phone}
                    onChangeText={setPhone}
                    placeholder="9876543210"
                    placeholderTextColor={Colors.neutral[400]}
                    keyboardType="phone-pad"
                    autoFocus
                    maxLength={15}
                    accessibilityLabel="Phone number"
                    returnKeyType="done"
                    onSubmitEditing={handleSendOtp}
                  />
                </View>
              ) : (
                <TextInput
                  style={[styles.inputWrapper, { paddingLeft: Spacing[4] }]}
                  value={email}
                  onChangeText={setEmail}
                  placeholder="you@example.com"
                  placeholderTextColor={Colors.neutral[400]}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoFocus
                  accessibilityLabel="Email address"
                  returnKeyType="done"
                  onSubmitEditing={handleSendOtp}
                />
              )}

              {error && <Text style={styles.errorText}>{error}</Text>}

              <TouchableOpacity
                style={[styles.primaryButton, !isInputValid && styles.primaryButtonDisabled]}
                onPress={handleSendOtp}
                disabled={!isInputValid}
                accessibilityRole="button"
                accessibilityLabel="Send OTP"
                accessibilityState={{ disabled: !isInputValid }}
              >
                <Text style={styles.primaryButtonText}>Send OTP →</Text>
              </TouchableOpacity>

              {/* Demo Mode / Instant Test Access */}
              <TouchableOpacity
                style={styles.demoButton}
                onPress={async () => {
                  setStep('loading');
                  try {
                    await demoLogin();
                    // Show transition briefly; auth guard in _layout.tsx handles navigation
                    setShowTransition(true);
                  } catch {
                    setStep('input');
                  }
                }}
                accessibilityRole="button"
                accessibilityLabel="Quick Demo Login"
              >
                <Text style={styles.demoButtonEmoji}>⚡</Text>
                <View>
                  <Text style={styles.demoButtonTitle}>Quick Demo Login (Ramesh Kumar)</Text>
                  <Text style={styles.demoButtonSubtitle}>Explore all citizen features instantly</Text>
                </View>
              </TouchableOpacity>

              <View style={styles.helpRow}>
                <TouchableOpacity accessibilityRole="link">
                  <Text style={styles.helpLink}>Need help?</Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            <>
              <Text style={styles.title}>Enter the code</Text>
              <Text style={styles.subtitle}>
                We sent a 6-digit code to{'\n'}
                <Text style={styles.subtitleBold}>{inputValue}</Text>
              </Text>

              {/* OTP boxes */}
              <View style={styles.otpRow}>
                {otp.map((digit, i) => (
                  <TextInput
                    key={i}
                    ref={ref => { otpRefs.current[i] = ref; }}
                    style={[styles.otpBox, digit !== '' && styles.otpBoxFilled]}
                    value={digit}
                    onChangeText={v => handleOtpChange(v.replace(/\D/g, '').slice(-1), i)}
                    onKeyPress={({ nativeEvent }) => handleOtpKeyPress(nativeEvent.key, i)}
                    keyboardType="number-pad"
                    maxLength={1}
                    textAlign="center"
                    accessibilityLabel={`OTP digit ${i + 1}`}
                    autoFocus={i === 0}
                  />
                ))}
              </View>

              {error && <Text style={styles.errorText}>{error}</Text>}

              <TouchableOpacity
                style={[styles.primaryButton, otp.join('').length < 6 && styles.primaryButtonDisabled]}
                onPress={handleVerifyOtp}
                disabled={otp.join('').length < 6}
                accessibilityRole="button"
                accessibilityLabel="Verify OTP"
              >
                <Text style={styles.primaryButtonText}>Verify →</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.resendButton}
                onPress={() => { setStep('input'); setOtp(['','','','','','']); }}
                accessibilityRole="button"
              >
                <Text style={styles.resendText}>Change number / Resend OTP</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.brand[800] },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[5],
    gap: Spacing[3],
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: Radii.md,
    backgroundColor: 'rgba(255,255,255,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backIcon: { color: '#fff', fontSize: 20 },
  logoBox: {
    width: 36,
    height: 36,
    borderRadius: Radii.sm,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoEmoji: { fontSize: 20 },
  headerTitle: {
    color: '#fff',
    fontSize: Typography.md,
    fontWeight: Typography.bold,
    letterSpacing: -0.4,
  },
  body: {
    flex: 1,
    backgroundColor: Colors.neutral[50],
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: Spacing[6],
    paddingTop: Spacing[8],
  },
  title: {
    fontSize: Typography['2xl'],
    fontWeight: Typography.extrabold,
    color: Colors.neutral[900],
    marginBottom: Spacing[2],
    letterSpacing: -0.6,
  },
  subtitle: {
    fontSize: Typography.base,
    color: Colors.neutral[500],
    lineHeight: 22,
    marginBottom: Spacing[6],
  },
  subtitleBold: {
    fontWeight: Typography.bold,
    color: Colors.neutral[700],
  },
  modeToggle: {
    flexDirection: 'row',
    backgroundColor: Colors.neutral[100],
    borderRadius: Radii.lg,
    padding: 4,
    marginBottom: Spacing[5],
  },
  modeTab: {
    flex: 1,
    paddingVertical: Spacing[2.5],
    alignItems: 'center',
    borderRadius: Radii.md,
  },
  modeTabActive: {
    backgroundColor: '#fff',
    ...Shadows.sm,
  },
  modeTabText: {
    fontSize: Typography.sm,
    fontWeight: Typography.medium,
    color: Colors.neutral[500],
  },
  modeTabTextActive: {
    color: Colors.brand[700],
    fontWeight: Typography.semibold,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderWidth: 1.5,
    borderColor: Colors.brand[200],
    borderRadius: Radii.lg,
    paddingRight: Spacing[4],
    marginBottom: Spacing[5],
    ...Shadows.sm,
  },
  inputPrefix: {
    paddingHorizontal: Spacing[4],
    paddingVertical: Spacing[4],
    fontSize: Typography.base,
    color: Colors.neutral[700],
    fontWeight: Typography.semibold,
    borderRightWidth: 1,
    borderRightColor: Colors.neutral[200],
    marginRight: Spacing[2],
  },
  textInput: {
    flex: 1,
    fontSize: Typography.base,
    color: Colors.neutral[900],
    paddingVertical: Spacing[4],
  },
  otpRow: {
    flexDirection: 'row',
    gap: Spacing[2],
    marginBottom: Spacing[6],
    justifyContent: 'space-between',
  },
  otpBox: {
    flex: 1,
    height: 56,
    backgroundColor: '#fff',
    borderWidth: 1.5,
    borderColor: Colors.neutral[200],
    borderRadius: Radii.lg,
    fontSize: Typography.xl,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    ...Shadows.sm,
  },
  otpBoxFilled: {
    borderColor: Colors.brand[400],
    backgroundColor: Colors.brand[50],
  },
  errorText: {
    fontSize: Typography.sm,
    color: Colors.error,
    marginBottom: Spacing[4],
    fontWeight: Typography.medium,
  },
  primaryButton: {
    backgroundColor: Colors.brand[600],
    borderRadius: Radii.xl,
    paddingVertical: Spacing[4],
    alignItems: 'center',
    ...Shadows.civic,
  },
  primaryButtonDisabled: {
    backgroundColor: Colors.neutral[300],
    shadowOpacity: 0,
  },
  primaryButtonText: {
    color: '#fff',
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    letterSpacing: -0.3,
  },
  demoButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: Radii.xl,
    paddingVertical: Spacing[3.5],
    paddingHorizontal: Spacing[4],
    marginTop: Spacing[3],
    borderWidth: 1.5,
    borderColor: Colors.brand[200],
    gap: Spacing[3],
    ...Shadows.sm,
  },
  demoButtonEmoji: {
    fontSize: 22,
  },
  demoButtonTitle: {
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
    color: Colors.brand[800],
  },
  demoButtonSubtitle: {
    fontSize: Typography.xs,
    color: Colors.neutral[500],
    marginTop: 1,
  },
  helpRow: {
    alignItems: 'center',
    marginTop: Spacing[5],
  },
  helpLink: {
    color: Colors.brand[600],
    fontSize: Typography.sm,
    fontWeight: Typography.medium,
  },
  resendButton: {
    alignItems: 'center',
    marginTop: Spacing[5],
    paddingVertical: Spacing[3],
  },
  resendText: {
    color: Colors.brand[600],
    fontSize: Typography.sm,
    fontWeight: Typography.medium,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing[4],
  },
  loadingText: {
    color: Colors.neutral[500],
    fontSize: Typography.base,
    fontWeight: Typography.medium,
  },
});
