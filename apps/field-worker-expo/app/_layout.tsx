import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="work-order/[id]" />
        <Stack.Screen name="work-order/start/[id]" />
        <Stack.Screen name="work-order/evidence/[id]" />
        <Stack.Screen name="work-order/complete/[id]" />
      </Stack>
    </>
  );
}
