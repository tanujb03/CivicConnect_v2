import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Pressable,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Radii, Shadows, Spacing, TouchTargets } from '../src/theme/tokens';
import { FontFamily } from '../src/theme/fonts';
import { Button, Field, Input, HardShadow, useToast } from '../src/ui';

// Mock: any Employee ID + PIN works for demo
const MOCK_EMPLOYEE_ID = 'RK-7041';
const MOCK_PIN = '1234';

export default function SignInScreen() {
  const { show } = useToast();
  const [employeeId, setEmployeeId] = useState('');
  const [pin, setPin] = useState('');
  const [pinVisible, setPinVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({ employeeId: '', pin: '' });

  const validate = () => {
    const newErrors = { employeeId: '', pin: '' };
    let valid = true;
    if (!employeeId.trim()) {
      newErrors.employeeId = 'Employee ID is required';
      valid = false;
    }
    if (!pin.trim() || pin.length < 4) {
      newErrors.pin = 'PIN must be at least 4 digits';
      valid = false;
    }
    setErrors(newErrors);
    return valid;
  };

  const handleSignIn = async () => {
    if (!validate()) return;
    setLoading(true);
    // Simulate network delay
    await new Promise((r) => setTimeout(r, 1200));
    setLoading(false);
    // Mock auth: accept any credentials for demo
    show('Welcome back, Ravi!', 'success');
    router.replace('/(tabs)');
  };

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <StatusBar style="light" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Hero header */}
          <View style={styles.hero}>
            <Text style={styles.eyebrow}>CIVICCONNECT</Text>
            <Text style={styles.heading}>FIELD{'\n'}WORKER</Text>
            <HardShadow offset={{ dx: 3, dy: 3 }} radius={Radii.full} containerStyle={styles.badgeWrapper}>
              <View style={styles.badge}>
                <Text style={styles.badgeText}>NAGPUR MUNICIPAL CORP.</Text>
              </View>
            </HardShadow>
          </View>

          {/* Sign-in form card */}
          <HardShadow offset={Shadows.card} radius={Radii.xl} containerStyle={styles.cardWrapper}>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>SIGN IN</Text>

              <Field
                label="Employee ID"
                error={errors.employeeId}
                required
                style={styles.fieldGap}
              >
                <Input
                  value={employeeId}
                  onChangeText={(t) => {
                    setEmployeeId(t.toUpperCase());
                    if (errors.employeeId) setErrors((e) => ({ ...e, employeeId: '' }));
                  }}
                  placeholder={MOCK_EMPLOYEE_ID}
                  autoCapitalize="characters"
                  returnKeyType="next"
                  hasError={!!errors.employeeId}
                  leftIcon={
                    <Ionicons name="id-card-outline" size={18} color={Colors.muted} />
                  }
                />
              </Field>

              <Field label="PIN" error={errors.pin} required style={styles.fieldGap}>
                <Input
                  value={pin}
                  onChangeText={(t) => {
                    setPin(t.replace(/\D/g, '').slice(0, 6));
                    if (errors.pin) setErrors((e) => ({ ...e, pin: '' }));
                  }}
                  placeholder="••••"
                  secureTextEntry={!pinVisible}
                  keyboardType="number-pad"
                  returnKeyType="done"
                  onSubmitEditing={handleSignIn}
                  hasError={!!errors.pin}
                  leftIcon={
                    <Ionicons name="lock-closed-outline" size={18} color={Colors.muted} />
                  }
                  rightIcon={
                    <Pressable
                      onPress={() => setPinVisible((v) => !v)}
                      hitSlop={8}
                      accessibilityLabel={pinVisible ? 'Hide PIN' : 'Show PIN'}
                    >
                      <Ionicons
                        name={pinVisible ? 'eye-off-outline' : 'eye-outline'}
                        size={18}
                        color={Colors.muted}
                      />
                    </Pressable>
                  }
                />
              </Field>

              <View style={styles.buttonRow}>
                <Button
                  title={loading ? 'Signing in...' : 'SIGN IN'}
                  onPress={handleSignIn}
                  variant="primary"
                  loading={loading}
                  accessibilityLabel="Sign in to the app"
                />
              </View>

              <Text style={styles.hint}>
                Demo: Any Employee ID + any 4-digit PIN
              </Text>
            </View>
          </HardShadow>

          {/* Version stamp */}
          <Text style={styles.version}>v1.0.0-beta</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: Colors.wine,
  },
  flex: {
    flex: 1,
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: Spacing.screenH,
    paddingBottom: 32,
  },
  hero: {
    paddingTop: 40,
    paddingBottom: 36,
  },
  eyebrow: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    fontWeight: '500',
    color: Colors.lime,
    letterSpacing: 2,
    marginBottom: 12,
  },
  heading: {
    fontFamily: FontFamily.display,
    fontSize: 52,
    color: Colors.onWine,
    lineHeight: 56,
    letterSpacing: -1,
    marginBottom: 20,
  },
  badgeWrapper: {
    alignSelf: 'flex-start',
  },
  badge: {
    backgroundColor: Colors.rust,
    borderWidth: 2,
    borderColor: Colors.ink,
    borderRadius: Radii.full,
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  badgeText: {
    fontFamily: FontFamily.mono,
    fontSize: 10,
    fontWeight: '500',
    color: Colors.onWine,
    letterSpacing: 1.5,
  },
  cardWrapper: {
    width: '100%',
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.xl,
    borderWidth: 2,
    borderColor: Colors.ink,
    padding: 24,
  },
  cardTitle: {
    fontFamily: FontFamily.display,
    fontSize: 22,
    color: Colors.ink,
    letterSpacing: 1,
    marginBottom: 24,
  },
  fieldGap: {
    marginBottom: 18,
  },
  buttonRow: {
    marginTop: 8,
  },
  hint: {
    fontFamily: FontFamily.sans,
    fontSize: 12,
    color: Colors.muted,
    textAlign: 'center',
    marginTop: 16,
  },
  version: {
    fontFamily: FontFamily.mono,
    fontSize: 11,
    color: Colors.rust,
    textAlign: 'center',
    marginTop: 24,
    letterSpacing: 1,
  },
});
