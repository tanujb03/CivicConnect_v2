/**
 * C09 — Notifications
 * Workflow events — each deep-links to the relevant entity.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Shadows, Layout } from '../../../src/constants/theme';
import { notificationsApi } from '../../../src/api/client';
import type { AppNotification, NotificationEventType } from '../../../src/types';

const EVENT_ICONS: Record<NotificationEventType, string> = {
  case_assigned:              '📋',
  case_in_progress:           '🔧',
  evidence_uploaded:          '📷',
  verification_requested:     '✅',
  case_resolved:              '🎉',
  case_reopened:              '🔄',
  duplicate_found:            '🔗',
  department_requested_info:  '❓',
  case_supported:             '👍',
  incident_nearby:            '⚠️',
};

const EVENT_COLORS: Record<NotificationEventType, string> = {
  case_assigned:              Colors.info,
  case_in_progress:           Colors.warning,
  evidence_uploaded:          Colors.brand[500],
  verification_requested:     Colors.success,
  case_resolved:              Colors.success,
  case_reopened:              Colors.error,
  duplicate_found:            '#8b5cf6',
  department_requested_info:  Colors.warning,
  case_supported:             Colors.brand[500],
  incident_nearby:            Colors.error,
};

const MOCK_NOTIFICATIONS: AppNotification[] = [
  {
    id: 'n1',
    title: 'Issue Status Updated',
    body: 'Your report "Large Pothole on Main Street" is now in progress',
    type: 'case_in_progress',
    read: false,
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    case_id: '1',
  },
  {
    id: 'n2',
    title: 'Issue Getting Attention',
    body: 'Your report has received 5+ upvotes from the community',
    type: 'case_supported',
    read: false,
    created_at: new Date(Date.now() - 3600000 * 18).toISOString(),
    case_id: '2',
  },
  {
    id: 'n3',
    title: 'Issue Resolved',
    body: 'Great news! "Street Light Not Working" has been resolved',
    type: 'case_resolved',
    read: true,
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    case_id: '3',
  },
  {
    id: 'n4',
    title: 'New Issue in Your Area',
    body: 'Water pipe leakage reported near your location in Ranchi',
    type: 'incident_nearby',
    read: true,
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
    case_id: '4',
  },
];

function NotificationItem({
  item,
  onPress,
  onMarkRead,
}: {
  item: AppNotification;
  onPress: () => void;
  onMarkRead: (id: string) => void;
}) {
  const icon = EVENT_ICONS[item.type] ?? '📢';
  const color = EVENT_COLORS[item.type] ?? Colors.neutral[400];
  const ago = getTimeAgo(item.created_at);

  return (
    <TouchableOpacity
      style={[
        styles.item,
        { borderLeftColor: color, borderLeftWidth: 4 },
        !item.read && styles.itemUnread,
      ]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={item.title}
    >
      <View style={[styles.iconBox, { backgroundColor: color + '15' }]}>
        <Text style={styles.icon}>{icon}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
          <Text style={[styles.itemTitle, !item.read && styles.itemTitleUnread]}>{item.title}</Text>
          {!item.read && (
            <TouchableOpacity
              onPress={(e) => {
                e.stopPropagation?.();
                onMarkRead(item.id);
              }}
              style={styles.checkBtn}
              accessibilityLabel="Mark as read"
            >
              <Text style={{ fontSize: 13, color: Colors.brand[600] }}>✓</Text>
            </TouchableOpacity>
          )}
        </View>
        <Text style={styles.itemBody} numberOfLines={2}>{item.body}</Text>
        <Text style={styles.itemTime}>{ago}</Text>
      </View>
      {!item.read && <View style={styles.unreadDot} />}
    </TouchableOpacity>
  );
}

export default function NotificationsScreen() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await notificationsApi.list(1);
      if (res.items && res.items.length > 0) {
        setNotifications(res.items);
      } else {
        setNotifications(MOCK_NOTIFICATIONS);
      }
    } catch {
      setNotifications(MOCK_NOTIFICATIONS);
    }
  }, []);

  useEffect(() => { load().finally(() => setLoading(false)); }, [load]);

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  async function handlePress(n: AppNotification) {
    if (!n.read) {
      await notificationsApi.markRead(n.id).catch(() => {});
      setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, read: true } : x));
    }
    if (n.case_id) router.push(`/(app)/case/${n.case_id}`);
  }

  function handleMarkRead(id: string) {
    setNotifications(prev => prev.map(x => x.id === id ? { ...x, read: true } : x));
  }

  async function markAllRead() {
    await notificationsApi.markAllRead().catch(() => {});
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  }

  function clearAll() {
    setNotifications([]);
  }

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Notifications</Text>
          <Text style={styles.headerSub}>
            {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
          </Text>
        </View>
        <View style={{ flexDirection: 'row', gap: Spacing[2] }}>
          {unreadCount > 0 && (
            <TouchableOpacity onPress={markAllRead} style={styles.markAllBtn}>
              <Text style={styles.markAllText}>Mark all read</Text>
            </TouchableOpacity>
          )}
          {notifications.length > 0 && (
            <TouchableOpacity onPress={clearAll} style={styles.clearBtn}>
              <Text style={styles.clearBtnText}>🗑️ Clear</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={Colors.brand[600]} /></View>
      ) : notifications.length === 0 ? (
        <View style={styles.center}>
          <Text style={{ fontSize: 48, marginBottom: Spacing[4] }}>🔔</Text>
          <Text style={styles.emptyTitle}>No notifications yet</Text>
          <Text style={styles.emptySub}>You'll receive updates about your reports and community activity here.</Text>
        </View>
      ) : (
        <FlatList
          data={notifications}
          keyExtractor={n => n.id}
          renderItem={({ item }) => (
            <NotificationItem
              item={item}
              onPress={() => handlePress(item)}
              onMarkRead={handleMarkRead}
            />
          )}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.brand[600]} />}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

function getTimeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.neutral[50] },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[5], paddingVertical: Spacing[4], backgroundColor: Colors.brand[800] },
  headerTitle: { fontSize: Typography.xl, fontWeight: Typography.bold, color: '#fff', letterSpacing: -0.4 },
  headerSub: { fontSize: Typography.xs, color: 'rgba(255,255,255,0.6)', marginTop: 2 },
  markAllBtn: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[2], backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: Radii.lg },
  markAllText: { fontSize: Typography.xs, color: '#fff', fontWeight: Typography.semibold },
  clearBtn: { paddingHorizontal: Spacing[3], paddingVertical: Spacing[2], backgroundColor: 'rgba(239,68,68,0.2)', borderRadius: Radii.lg },
  clearBtnText: { fontSize: Typography.xs, color: '#fca5a5', fontWeight: Typography.semibold },
  list: { paddingHorizontal: Spacing[5], paddingTop: Spacing[3], paddingBottom: Layout.bottomNavHeight + Spacing[4] },
  item: { flexDirection: 'row', gap: Spacing[3], alignItems: 'flex-start', backgroundColor: '#fff', borderRadius: Radii.xl, padding: Spacing[4], marginBottom: Spacing[2], ...Shadows.sm, borderWidth: 1, borderColor: Colors.neutral[100] },
  itemUnread: { backgroundColor: '#fff' },
  iconBox: { width: 44, height: 44, borderRadius: Radii.lg, alignItems: 'center', justifyContent: 'center' },
  icon: { fontSize: 22 },
  itemTitle: { fontSize: Typography.sm, fontWeight: Typography.semibold, color: Colors.neutral[700], marginBottom: 2 },
  itemTitleUnread: { color: Colors.neutral[900], fontWeight: Typography.bold },
  itemBody: { fontSize: Typography.xs, color: Colors.neutral[500], lineHeight: 16, marginBottom: 4 },
  itemTime: { fontSize: 10, color: Colors.neutral[400], fontWeight: Typography.medium },
  checkBtn: { width: 22, height: 22, borderRadius: 11, backgroundColor: Colors.brand[50], alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: Colors.brand[200] },
  unreadDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.brand[500], marginTop: 6 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing[3], paddingHorizontal: Spacing[8] },
  emptyTitle: { fontSize: Typography.xl, fontWeight: Typography.bold, color: Colors.neutral[900] },
  emptySub: { fontSize: Typography.base, color: Colors.neutral[400], textAlign: 'center', lineHeight: 22 },
});
