/**
 * C09 — Notifications
 * Workflow events — each deep-links to the relevant entity.
 * Restyled for Direction A (ink borders, hard shadows, lime/wine/fire palette).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Layout } from '../../../src/constants/theme';
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
  const ago = getTimeAgo(item.created_at);

  return (
    <View style={styles.itemOuter}>
      <View style={styles.itemShadow} />
      <TouchableOpacity
        style={[styles.item, !item.read && styles.itemUnread]}
        onPress={onPress}
        activeOpacity={0.9}
        accessibilityRole="button"
        accessibilityLabel={item.title}
      >
        <View style={styles.iconBox}>
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
                <Text style={{ fontSize: 13, color: Colors.ink }}>✓</Text>
              </TouchableOpacity>
            )}
          </View>
          <Text style={styles.itemBody} numberOfLines={2}>{item.body}</Text>
          <Text style={styles.itemTime}>{ago}</Text>
        </View>
        {!item.read && <View style={styles.unreadDot} />}
      </TouchableOpacity>
    </View>
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
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>C09 • NOTIFICATIONS</Text>
        <View style={{ width: 44 }} />
      </View>

      <View style={styles.actionsRow}>
        <Text style={styles.unreadLabel}>
          {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up ✓'}
        </Text>
        <View style={{ flexDirection: 'row', gap: Spacing[2] }}>
          {unreadCount > 0 && (
            <TouchableOpacity onPress={markAllRead} style={styles.actionBtn}>
              <Text style={styles.actionBtnText}>Mark all read</Text>
            </TouchableOpacity>
          )}
          {notifications.length > 0 && (
            <TouchableOpacity onPress={clearAll} style={[styles.actionBtn, { backgroundColor: Colors.fire }]}>
              <Text style={[styles.actionBtnText, { color: Colors.surface }]}>Clear</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={Colors.ink} /></View>
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
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.ink} />}
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
  container: { flex: 1, backgroundColor: Colors.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], paddingVertical: Spacing[4] },
  backBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: Colors.ink, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface },
  backBtnText: { fontSize: 18, color: Colors.ink },
  headerTitle: { fontFamily: 'monospace', fontSize: 14, fontWeight: Typography.bold, color: Colors.muted },
  actionsRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing[4], marginBottom: Spacing[4] },
  unreadLabel: { fontSize: 16, fontWeight: Typography.bold, color: Colors.ink },
  actionBtn: { backgroundColor: Colors.lime, paddingHorizontal: Spacing[3], paddingVertical: Spacing[1.5], borderRadius: Radii.full, borderWidth: 1.5, borderColor: Colors.ink },
  actionBtnText: { fontSize: 12, fontWeight: Typography.bold, color: Colors.ink },
  list: { paddingHorizontal: Spacing[4], paddingBottom: Layout.bottomNavHeight + Spacing[4] },
  itemOuter: { marginBottom: Spacing[3] },
  itemShadow: { position: 'absolute', top: 4, left: 4, right: -4, bottom: -4, backgroundColor: Colors.ink, borderRadius: Radii.lg },
  item: { flexDirection: 'row', gap: Spacing[3], alignItems: 'flex-start', backgroundColor: Colors.surface, borderRadius: Radii.lg, padding: Spacing[4], borderWidth: 2, borderColor: Colors.ink },
  itemUnread: { backgroundColor: Colors.limeTint },
  iconBox: { width: 44, height: 44, borderRadius: Radii.lg, backgroundColor: Colors.ground, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: Colors.ink },
  icon: { fontSize: 22 },
  itemTitle: { fontSize: 14, fontWeight: Typography.semibold, color: Colors.muted, marginBottom: 2 },
  itemTitleUnread: { color: Colors.ink, fontWeight: Typography.bold },
  itemBody: { fontSize: 13, color: Colors.muted, lineHeight: 18, marginBottom: 4 },
  itemTime: { fontSize: 10, color: Colors.muted, fontWeight: Typography.medium },
  checkBtn: { width: 22, height: 22, borderRadius: 11, backgroundColor: Colors.lime, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: Colors.ink },
  unreadDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.fire, marginTop: 6, borderWidth: 1, borderColor: Colors.ink },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing[3], paddingHorizontal: Spacing[8] },
  emptyTitle: { fontSize: 20, fontWeight: Typography.bold, color: Colors.ink },
  emptySub: { fontSize: 15, color: Colors.muted, textAlign: 'center', lineHeight: 22 },
});
