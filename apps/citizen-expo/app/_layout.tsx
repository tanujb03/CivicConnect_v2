import React, { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { AuthProvider, useAuthContext } from '../src/context/AuthContext';
import { OfflineProvider } from '../src/context/OfflineContext';
import { AppSettingsProvider } from '../src/context/AppSettingsContext';

function RootLayoutNav() {
  const { isAuthenticated, isLoading } = useAuthContext();
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';
    const inAppGroup = segments[0] === '(app)';

    if (!isAuthenticated && !inAuthGroup) {
      router.replace('/(auth)/welcome');
    } else if (isAuthenticated && inAuthGroup) {
      router.replace('/(app)/(tabs)/dashboard');
    }
  }, [isAuthenticated, isLoading, segments]);

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="(app)" />
    </Stack>
  );
}

import { View, StyleSheet, Platform } from 'react-native';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={styles.rootGesture}>
      <SafeAreaProvider>
        <AppSettingsProvider>
          <AuthProvider>
            <OfflineProvider>
              <StatusBar style="dark" />
              <View style={styles.shellOuter}>
                <View style={styles.shellInner}>
                  <RootLayoutNav />
                </View>
              </View>
            </OfflineProvider>
          </AuthProvider>
        </AppSettingsProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  rootGesture: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  shellOuter: {
    flex: 1,
    width: '100%',
    backgroundColor: Platform.OS === 'web' ? '#0F172A' : '#F8FAFC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  shellInner: {
    flex: 1,
    width: '100%',
    maxWidth: Platform.OS === 'web' ? 480 : undefined,
    backgroundColor: '#FFFFFF',
    overflow: 'hidden',
    ...(Platform.OS === 'web'
      ? {
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 10 },
          shadowOpacity: 0.3,
          shadowRadius: 20,
        }
      : {}),
  },
});
