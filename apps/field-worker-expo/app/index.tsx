import { Redirect } from 'expo-router';

// Root index: immediately redirect to tabs
export default function Index() {
  return <Redirect href="/(tabs)" />;
}
