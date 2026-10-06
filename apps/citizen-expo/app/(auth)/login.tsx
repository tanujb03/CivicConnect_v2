/**
 * C02 — Authentication (Login)
 * Direction A aesthetic: ink borders, hard shadows, lime/wine/fire palette.
 */

import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, ActivityIndicator, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii } from '../../src/constants/theme';
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
  const [selectedRole] = useState<'citizen' | 'field_worker'>('citizen');
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
      await requestOtp(inputMode === 'phone' ? { phone: phone.trim() } : { email: email.trim() });
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
      <StatusBar style="dark" />

      <Modal visible={showTransition} transparent animationType="fade">
        <TransitionScreen
          role={selectedRole}
          onComplete={() => {
            setShowTransition(false);
            router.replace('/(app)/(tabs)/dashboard');
          }}
        />
      </Modal>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity
            onPress={() => {
              if (step === 'otp') { setStep('input'); setOtp(['','','','','','']); }
              else router.back();
            }}
            style={styles.backBtn}
          >
            <Text style={styles.backBtnText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>CivicConnect</Text>
          <View style={{ width: 44 }} />
        </View>

        <View style={styles.body}>
          {step === 'loading' ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={Colors.ink} />
              <Text style={styles.loadingText}>Please wait…</Text>
            </View>
          ) : step === 'input' ? (
            <>
              <Text style={styles.title}>SIGN IN</Text>
              <Text style={styles.subtitle}>
                Enter your phone number or email. We'll send you a one-time code.
              </Text>

              <View style={styles.modeToggle}>
                <TouchableOpacity
                  style={[styles.modeTab, inputMode === 'phone' && styles.modeTabActive]}
                  onPress={() => setInputMode('phone')}
                >
                  <Text style={[styles.modeTabText, inputMode === 'phone' && styles.modeTabTextActive]}>📱 Phone</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.modeTab, inputMode === 'email' && styles.modeTabActive]}
                  onPress={() => setInputMode('email')}
                >
                  <Text style={[styles.modeTabText, inputMode === 'email' && styles.modeTabTextActive]}>✉️ Email</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.inputOuter}>
                <View style={styles.inputShadow} />
                {inputMode === 'phone' ? (
                  <View style={styles.inputWrapper}>
                    <Text style={styles.inputPrefix}>+91</Text>
                    <TextInput
                      style={styles.textInput}
                      value={phone}
                      onChangeText={setPhone}
                      placeholder="9876543210"
                      placeholderTextColor={Colors.muted}
                      keyboardType="phone-pad"
                      autoFocus
                      maxLength={15}
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
                    placeholderTextColor={Colors.muted}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoFocus
                    returnKeyType="done"
                    onSubmitEditing={handleSendOtp}
                  />
                )}
              </View>

              {error && <Text style={styles.errorText}>{error}</Text>}

              <View style={styles.sendBtnOuter}>
                <View style={styles.sendBtnShadow} />
                <TouchableOpacity
                  style={[styles.sendBtn, !isInputValid && styles.sendBtnDisabled]}
                  onPress={handleSendOtp}
                  disabled={!isInputValid}
                >
                  <Text style={styles.sendBtnText}>Send OTP</Text>
                  <View style={styles.sendBtnArrow}>
                    <Text style={styles.sendBtnArrowText}>→</Text>
                  </View>
                </TouchableOpacity>
              </View>

              <TouchableOpacity
                style={styles.demoButton}
                onPress={async () => {
                  setStep('loading');
                  try {
                    await demoLogin();
                    setShowTransition(true);
                  } catch {
                    setStep('input');
                  }
                }}
              >
                <Text style={styles.demoEmoji}>⚡</Text>
                <View>
                  <Text style={styles.demoTitle}>Quick Demo Login (Ramesh Kumar)</Text>
                  <Text style={styles.demoSub}>Explore all citizen features instantly</Text>
                </View>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.title}>ENTER CODE</Text>
              <Text style={styles.subtitle}>
                We sent a 6-digit code to{'\n'}
                <Text style={styles.subtitleBold}>{inputValue}</Text>
              </Text>

              <View style={styles.otpRow}>
                {otp.map((digit, i) => (
                  <View key={i} style={styles.otpBoxOuter}>
                    <View style={styles.otpBoxShadow} />
                    <TextInput
                      ref={ref => { otpRefs.current[i] = ref; }}
                      style={[styles.otpBox, digit !== '' && styles.otpBoxFilled]}
                      value={digit}
                      onChangeText={v => handleOtpChange(v.replace(/\D/g, '').slice(-1), i)}
                      onKeyPress={({ nativeEvent }) => handleOtpKeyPress(nativeEvent.key, i)}
                      keyboardType="number-pad"
                      maxLength={1}
                      textAlign="center"
                      autoFocus={i === 0}
                    />
                  </View>
                ))}
              </View>

              {error && <Text style={styles.errorText}>{error}</Text>}

              <View style={styles.sendBtnOuter}>
                <View style={styles.sendBtnShadow} />
                <TouchableOpacity
                  style={[styles.sendBtn, otp.join('').length < 6 && styles.sendBtnDisabled]}
                  onPress={handleVerifyOtp}
                  disabled={otp.join('').length < 6}
                >
                  <Text style={styles.sendBtnText}>Verify</Text>
                  <View style={styles.sendBtnArrow}>
                    <Text style={styles.sendBtnArrowText}>→</Text>
                  </View>
                </TouchableOpacity>
              </View>

              <TouchableOpacity
                style={styles.resendButton}
                onPress={() => { setStep('input'); setOtp(['','','','','','']); }}
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
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4] },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  body: { flex: 1, paddingHorizontal: Spacing[5], paddingTop: Spacing[6] },
  title: { fontSize: 42, fontWeight: Typography.black, color: Colors.ink, letterSpacing: -1, marginBottom: Spacing[2] },
  subtitle: { fontSize: 15, color: Colors.muted, lineHeight: 22, marginBottom: Spacing[6] },
  subtitleBold: { fontWeight: Typography.bold, color: Colors.ink },
  modeToggle: { flexDirection: 'row', backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: 4, marginBottom: Spacing[5], borderWidth: 2, borderColor: Colors.ink },
  modeTab: { flex: 1, paddingVertical: Spacing[2.5], alignItems: 'center', borderRadius: Radii.md },
  modeTabActive: { backgroundColor: Colors.lime },
  modeTabText: { fontSize: 14, fontWeight: Typography.medium, color: Colors.muted },
  modeTabTextActive: { color: Colors.ink, fontWeight: Typography.bold },
  inputOuter: { marginBottom: Spacing[5] },
  inputShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  inputWrapper: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, paddingRight: Spacing[4] },
  inputPrefix: { paddingHorizontal: Spacing[4], paddingVertical: Spacing[4], fontSize: 15, color: Colors.ink, fontWeight: Typography.bold, borderRightWidth: 2, borderRightColor: Colors.ink, marginRight: Spacing[2] },
  textInput: { flex: 1, fontSize: 15, color: Colors.ink, paddingVertical: Spacing[4] },
  errorText: { fontSize: 13, color: Colors.fire, marginBottom: Spacing[4], fontWeight: Typography.medium },
  sendBtnOuter: { marginBottom: Spacing[4] },
  sendBtnShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  sendBtn: { backgroundColor: Colors.lime, borderRadius: Radii.lg, paddingVertical: Spacing[3], paddingHorizontal: Spacing[4], flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 2, borderColor: Colors.ink },
  sendBtnDisabled: { backgroundColor: Colors.dot, opacity: 0.6 },
  sendBtnText: { color: Colors.ink, fontSize: 18, fontWeight: Typography.bold },
  sendBtnArrow: { width: 32, height: 32, borderRadius: 16, backgroundColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  sendBtnArrowText: { color: Colors.lime, fontWeight: Typography.bold, fontSize: 16 },
  demoButton: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radii.lg, paddingVertical: Spacing[3.5], paddingHorizontal: Spacing[4], marginTop: Spacing[2], borderWidth: 2, borderColor: Colors.ink, gap: Spacing[3] },
  demoEmoji: { fontSize: 22 },
  demoTitle: { fontSize: 14, fontWeight: Typography.bold, color: Colors.ink },
  demoSub: { fontSize: 12, color: Colors.muted, marginTop: 1 },
  otpRow: { flexDirection: 'row', gap: Spacing[2], marginBottom: Spacing[6], justifyContent: 'space-between' },
  otpBoxOuter: { flex: 1 },
  otpBoxShadow: { position: 'absolute', top: 3, left: 3, right: -3, bottom: -3, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  otpBox: { height: 56, backgroundColor: Colors.surface, borderWidth: 2, borderColor: Colors.ink, borderRadius: Radii.lg, fontSize: 20, fontWeight: Typography.bold, color: Colors.ink },
  otpBoxFilled: { backgroundColor: Colors.limeTint },
  resendButton: { alignItems: 'center', marginTop: Spacing[3], paddingVertical: Spacing[3] },
  resendText: { color: Colors.ink, fontSize: 14, fontWeight: Typography.medium, textDecorationLine: 'underline' },
  loadingContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing[4] },
  loadingText: { color: Colors.muted, fontSize: 15, fontWeight: Typography.medium },
});
