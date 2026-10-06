import { Stack } from 'expo-router';

export default function AppLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="report/index" options={{ presentation: 'modal' }} />
      <Stack.Screen name="case/[id]" />
      <Stack.Screen name="map/expanded" />
      <Stack.Screen name="settings/accessibility" />
      <Stack.Screen name="settings/language" />
      <Stack.Screen name="settings/profile" />
    </Stack>
  );
}
