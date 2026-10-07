import React from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/theme/tokens';
import { FontFamily } from '../../src/theme/fonts';

function TabIcon({
  name,
  color,
}: {
  name: string;
  color: string | any;
  focused?: boolean;
}) {
  return (
    <Ionicons
      name={name as any}
      size={22}
      color={color as string}
    />
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: Colors.wine,
        tabBarInactiveTintColor: Colors.muted,
        tabBarStyle: {
          backgroundColor: Colors.ground,
          borderTopWidth: 2,
          borderTopColor: Colors.ink,
          height: 64,
          paddingBottom: 10,
          paddingTop: 6,
        },
        tabBarLabelStyle: {
          fontFamily: FontFamily.mono,
          fontSize: 10,
          fontWeight: '500',
          letterSpacing: 0.5,
          textTransform: 'uppercase',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Assigned',
          tabBarIcon: ({ color, focused }) => (
            <TabIcon
              name={focused ? 'list-circle' : 'list-circle-outline'}
              color={color}
              focused={focused}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'Done',
          tabBarIcon: ({ color, focused }) => (
            <TabIcon
              name={focused ? 'checkmark-circle' : 'checkmark-circle-outline'}
              color={color}
              focused={focused}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Me',
          tabBarIcon: ({ color, focused }) => (
            <TabIcon
              name={focused ? 'person-circle' : 'person-circle-outline'}
              color={color}
              focused={focused}
            />
          ),
        }}
      />
    </Tabs>
  );
}
