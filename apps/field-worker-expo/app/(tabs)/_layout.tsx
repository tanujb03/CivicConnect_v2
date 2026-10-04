import React from 'react';
import { Tabs } from 'expo-router';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing } from '../../src/constants/theme';

function TabIcon({ emoji, label, focused }: { emoji: string; label: string; focused: boolean }) {
  return (
    <View style={styles.tabItem}>
      <Text style={[styles.emoji, focused && styles.emojiFocused]}>{emoji}</Text>
      <Text style={[styles.label, focused && styles.labelFocused]}>{label}</Text>
    </View>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarShowLabel: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="🛠️" label="Assigned Tasks" focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="📋" label="Work History" focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="👷" label="Shift & Crew" focused={focused} />
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    height: 64,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 2,
    borderTopColor: Colors.neutral[200],
    paddingTop: Spacing.xs,
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
  },
  emoji: {
    fontSize: 20,
    opacity: 0.6,
  },
  emojiFocused: {
    opacity: 1,
    transform: [{ scale: 1.1 }],
  },
  label: {
    fontSize: Typography.labelSmall.fontSize,
    color: Colors.neutral[500],
    fontWeight: '600',
  },
  labelFocused: {
    color: Colors.action[700],
    fontWeight: '700',
  },
});
