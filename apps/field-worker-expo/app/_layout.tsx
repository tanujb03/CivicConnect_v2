import 'react-native-gesture-handler';
import { useEffect } from 'react';
import { Stack, router } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StyleSheet, View } from 'react-native';
import { useAppFonts } from '../src/theme/fonts';
import { Colors } from '../src/theme/tokens';
import { ToastProvider } from '../src/ui/Toast';

// Create a single QueryClient for the app lifetime
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 2,
    },
  },
});

export default function RootLayout() {
  const [fontsLoaded, fontError] = useAppFonts();

  // Prevent rendering until fonts are ready
  if (!fontsLoaded && !fontError) {
    return (
      <View style={[StyleSheet.absoluteFill, { backgroundColor: Colors.wine }]} />
    );
  }

  return (
    <GestureHandlerRootView style={styles.root}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <StatusBar style="light" />
            <Stack screenOptions={{ headerShown: false }}>
              <Stack.Screen name="sign-in" options={{ animation: 'fade' }} />
              <Stack.Screen name="(tabs)" options={{ animation: 'fade' }} />
              <Stack.Screen
                name="work-order/[id]"
                options={{ animation: 'slide_from_right' }}
              />
              <Stack.Screen
                name="work-order/start/[id]"
                options={{ animation: 'slide_from_bottom', presentation: 'modal' }}
              />
              <Stack.Screen
                name="work-order/evidence/[id]"
                options={{ animation: 'slide_from_bottom', presentation: 'modal' }}
              />
              <Stack.Screen
                name="work-order/complete/[id]"
                options={{ animation: 'slide_from_bottom', presentation: 'modal' }}
              />
              <Stack.Screen
                name="dev/primitives"
                options={{ animation: 'slide_from_right' }}
              />
            </Stack>
          </ToastProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
});
