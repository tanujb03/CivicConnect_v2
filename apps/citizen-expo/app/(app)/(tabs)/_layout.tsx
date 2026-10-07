import React from 'react';
import { Tabs } from 'expo-router';
import { View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';
import { useOffline } from '../../../src/context/OfflineContext';
import { useRouter } from 'expo-router';

/**
 * Custom tab bar to guarantee perfect centering of the FAB
 * and even spacing of all tab icons.
 */
function CustomTabBar({ state, descriptors, navigation }: any) {
  const router = useRouter();

  // The visible tabs in order: dashboard, my-cases, map, community
  // We explicitly ignore __report_placeholder for the flex layout and render the FAB absolutely.
  const mainTabs = state.routes.filter(
    (r: any) => !['profile', 'notifications', '__report_placeholder'].includes(r.name)
  );

  return (
    <View style={tbStyles.container}>
      <View style={tbStyles.bar}>
        {/* Left tabs: dashboard, my-cases */}
        <View style={tbStyles.tabGroup}>
          {mainTabs.slice(0, 2).map((route: any, index: number) => {
            const focused = state.index === state.routes.indexOf(route);
            const iconMap: Record<string, string> = { dashboard: '⌂', 'my-cases': '☰' };
            const labelMap: Record<string, string> = { dashboard: 'Home', 'my-cases': 'Cases' };
            
            return (
              <TouchableOpacity
                key={route.key}
                style={tbStyles.tabColumn}
                onPress={() => navigation.navigate(route.name)}
                activeOpacity={0.7}
              >
                <View style={[tbStyles.iconCircle, focused && tbStyles.iconCircleActive]}>
                  <Text style={[tbStyles.icon, focused && tbStyles.iconActive]}>
                    {iconMap[route.name]}
                  </Text>
                </View>
                <Text style={[tbStyles.label, focused && tbStyles.labelActive]}>
                  {labelMap[route.name]}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Center Space for FAB */}
        <View style={tbStyles.centerSpace} />

        {/* Right tabs: map, community */}
        <View style={tbStyles.tabGroup}>
          {mainTabs.slice(2, 4).map((route: any, index: number) => {
            const focused = state.index === state.routes.indexOf(route);
            const iconMap: Record<string, string> = { map: '◎', community: '♺' };
            const labelMap: Record<string, string> = { map: 'Map', community: 'Community' };

            return (
              <TouchableOpacity
                key={route.key}
                style={tbStyles.tabColumn}
                onPress={() => navigation.navigate(route.name)}
                activeOpacity={0.7}
              >
                <View style={[tbStyles.iconCircle, focused && tbStyles.iconCircleActive]}>
                  <Text style={[tbStyles.icon, focused && tbStyles.iconActive]}>
                    {iconMap[route.name]}
                  </Text>
                </View>
                <Text style={[tbStyles.label, focused && tbStyles.labelActive]}>
                  {labelMap[route.name]}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Absolutely positioned FAB */}
      <View style={tbStyles.fabWrapper} pointerEvents="box-none">
        <TouchableOpacity
          onPress={() => router.push('/(app)/report')}
          activeOpacity={0.85}
          style={tbStyles.fabTouchable}
        >
          <View style={tbStyles.fabShadow} />
          <View style={tbStyles.fabCircle}>
            <Text style={tbStyles.fabPlus}>+</Text>
          </View>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const tbStyles = StyleSheet.create({
  container: {
    backgroundColor: 'transparent',
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: Layout.bottomNavHeight + 30, // Extra space for FAB popout
    justifyContent: 'flex-end',
  },
  bar: {
    flexDirection: 'row',
    height: Layout.bottomNavHeight,
    backgroundColor: Colors.surface,
    borderTopWidth: 3,
    borderTopColor: Colors.ink,
    paddingBottom: Platform.OS === 'ios' ? 20 : 8,
  },
  tabGroup: {
    flex: 1,
    flexDirection: 'row',
  },
  centerSpace: {
    width: 70, // Exact width to clear the FAB
  },
  tabColumn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 10,
  },
  iconCircle: {
    width: 42,
    height: 42,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCircleActive: {
    backgroundColor: Colors.lime,
    borderWidth: 2,
    borderColor: Colors.ink,
  },
  icon: {
    fontSize: 22,
    color: Colors.muted,
  },
  iconActive: {
    color: Colors.ink,
  },
  label: {
    fontSize: 10,
    fontWeight: Typography.bold,
    color: Colors.muted,
    marginTop: 2,
  },
  labelActive: {
    color: Colors.ink,
  },
  fabWrapper: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'flex-start', // aligns to top of the 85+30 container
  },
  fabTouchable: {
    width: 60,
    height: 60,
    marginTop: 5,
  },
  fabShadow: {
    position: 'absolute',
    top: 4,
    left: 4,
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Colors.ink,
  },
  fabCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Colors.lime,
    borderWidth: 3,
    borderColor: Colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fabPlus: {
    fontSize: 34,
    fontWeight: '900',
    color: Colors.ink,
    lineHeight: 36,
    textAlign: 'center',
  },
});

export default function TabsLayout() {
  const { isOnline, pendingCount } = useOffline();

  return (
    <View style={{ flex: 1, backgroundColor: Colors.ground }}>
      {!isOnline && (
        <View style={styles.offlineBanner}>
          <Text style={styles.offlineBannerText}>
            📶 Offline — {pendingCount > 0 ? `${pendingCount} reports queued` : 'changes will sync when reconnected'}
          </Text>
        </View>
      )}

      <Tabs
        tabBar={(props) => <CustomTabBar {...props} />}
        screenOptions={{ headerShown: false }}
      >
        <Tabs.Screen name="dashboard" />
        <Tabs.Screen name="my-cases" />
        <Tabs.Screen name="__report_placeholder" />
        <Tabs.Screen name="map" />
        <Tabs.Screen name="community" />
        <Tabs.Screen name="profile" />
        <Tabs.Screen name="notifications" />
      </Tabs>
    </View>
  );
}

const styles = StyleSheet.create({
  offlineBanner: {
    backgroundColor: Colors.amber,
    paddingVertical: Spacing[2],
    paddingHorizontal: Spacing[4],
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: Colors.ink,
  },
  offlineBannerText: {
    color: Colors.ink,
    fontSize: 13,
    fontWeight: Typography.bold,
  },
});
