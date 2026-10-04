import React from 'react';
import { Redirect } from 'expo-router';
import { useAuthContext } from '../src/context/AuthContext';
import { View, ActivityIndicator } from 'react-native';
import { Colors } from '../src/constants/theme';

/**
 * Root redirect — app entry point.
 * Directs authenticated citizens straight to dashboard, otherwise to welcome.
 */
export default function Index() {
  const { isAuthenticated, isLoading } = useAuthContext();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F8FAFC' }}>
        <ActivityIndicator size="large" color={Colors.brand[600]} />
      </View>
    );
  }

  return <Redirect href={isAuthenticated ? "/(app)/(tabs)/dashboard" : "/(auth)/welcome"} />;
}

