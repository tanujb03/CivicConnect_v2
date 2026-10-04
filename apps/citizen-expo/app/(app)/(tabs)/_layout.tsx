import React from 'react';
import { Tabs } from 'expo-router';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Colors, Typography, Spacing, Radii, Shadows, Layout } from '../../../src/constants/theme';
import { useOffline } from '../../../src/context/OfflineContext';
import { useRouter } from 'expo-router';

const TAB_ICONS: Record<string, string> = {
  dashboard: '🏠',
  'my-cases': '📋',
  community: '🤝',
  map: '🗺️',
  profile: '👤',
};

const TAB_LABELS: Record<string, string> = {
  dashboard: 'Home',
  'my-cases': 'My Cases',
  community: 'Community',
  map: 'Map',
  profile: 'Profile',
};

// Tabs that should be hidden from the tab bar (accessible via router.push)
const HIDDEN_TABS = ['notifications'];

function TabBarIcon({ name, focused }: { name: string; focused: boolean }) {
  return (
    <View style={[styles.tabIconWrapper, focused && styles.tabIconActive]}>
      <Text style={styles.tabEmoji}>{TAB_ICONS[name] ?? '●'}</Text>
      <Text style={[styles.tabLabel, focused && styles.tabLabelActive]}>
        {TAB_LABELS[name] ?? name}
      </Text>
    </View>
  );
}

function ReportFAB() {
  const router = useRouter();
  return (
    <TouchableOpacity
      style={styles.fab}
      onPress={() => router.push('/(app)/report')}
      accessibilityRole="button"
      accessibilityLabel="Report a civic issue"
    >
      <Text style={styles.fabIcon}>＋</Text>
    </TouchableOpacity>
  );
}

export default function TabsLayout() {
  const { isOnline, pendingCount } = useOffline();

  return (
    <>
      {/* Offline banner */}
      {!isOnline && (
        <View style={styles.offlineBanner}>
          <Text style={styles.offlineBannerText}>
            📶 Offline — {pendingCount > 0 ? `${pendingCount} reports queued` : 'changes will sync when reconnected'}
          </Text>
        </View>
      )}

      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarStyle: styles.tabBar,
          tabBarShowLabel: false,
        }}
      >
        <Tabs.Screen
          name="dashboard"
          options={{
            tabBarIcon: ({ focused }) => <TabBarIcon name="dashboard" focused={focused} />,
          }}
        />
        <Tabs.Screen
          name="my-cases"
          options={{
            tabBarIcon: ({ focused }) => <TabBarIcon name="my-cases" focused={focused} />,
          }}
        />
        <Tabs.Screen
          name="__report_placeholder"
          options={{
            tabBarButton: () => <ReportFAB />,
          }}
        />
        <Tabs.Screen
          name="community"
          options={{
            tabBarIcon: ({ focused }) => <TabBarIcon name="community" focused={focused} />,
          }}
        />
        <Tabs.Screen
          name="map"
          options={{
            tabBarIcon: ({ focused }) => <TabBarIcon name="map" focused={focused} />,
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            tabBarIcon: ({ focused }) => <TabBarIcon name="profile" focused={focused} />,
          }}
        />
        {/* Hidden tabs — navigable via router.push but not shown in tab bar */}
        <Tabs.Screen
          name="notifications"
          options={{ tabBarButton: () => null, tabBarStyle: { display: 'none' } }}
        />
      </Tabs>
    </>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    height: Layout.bottomNavHeight,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: Colors.neutral[100],
    paddingBottom: 0,
    ...Shadows.md,
  },
  tabIconWrapper: {
    alignItems: 'center',
    paddingTop: Spacing[2],
    gap: 2,
    minWidth: 48,
    minHeight: 44,
  },
  tabIconActive: {},
  tabEmoji: { fontSize: 22 },
  tabLabel: {
    fontSize: 10,
    fontWeight: Typography.medium,
    color: Colors.neutral[400],
  },
  tabLabelActive: {
    color: Colors.brand[600],
    fontWeight: Typography.semibold,
  },
  fab: {
    width: 56,
    height: 56,
    borderRadius: 18,
    backgroundColor: Colors.brand[600],
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -16,
    ...Shadows.civic,
  },
  fabIcon: {
    fontSize: 28,
    color: '#fff',
    fontWeight: Typography.bold,
    lineHeight: 32,
  },
  offlineBanner: {
    backgroundColor: Colors.warning,
    paddingVertical: Spacing[2],
    paddingHorizontal: Spacing[4],
    alignItems: 'center',
  },
  offlineBannerText: {
    color: '#fff',
    fontSize: Typography.sm,
    fontWeight: Typography.semibold,
  },
});
