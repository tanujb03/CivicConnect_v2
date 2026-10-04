/**
 * C04 — Citizen Dashboard
 *
 * Fully feature-matched with Citizen Web App + System Design:
 * - Header with User Locality & 3 Civic Intelligence Stat Cards (Total Issues, Resolved, Avg Response)
 * - Hero "Report an Issue" CTA card
 * - "Issues Near You" Map Section with Category Filter Pills ('all', 'roads', 'sanitation', 'water', 'lighting'),
 *   interactive markers with status colors & selection card, and "Expand →" full map link
 * - Attention / Action Items
 * - Quick Actions
 * - Awaiting Citizen Action cases
 * - Active Cases List
 * - Civic News Carousel with photos & descriptions
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Image,
  Dimensions,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Typography, Spacing, Radii, Shadows, Layout, STATUS_LABELS, CATEGORY_ICONS, PRIORITY_LABELS } from '../../../src/constants/theme';
import { useAuthContext } from '../../../src/context/AuthContext';
import { useOffline } from '../../../src/context/OfflineContext';
import { casesApi, notificationsApi } from '../../../src/api/client';
import { MOCK_STATS, MOCK_NEWS, MOCK_CASES, CivicNewsItem } from '../../../src/data/mockData';
import type { CivicCase, AppNotification, IssueCategory } from '../../../src/types';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// ─── Shared UI primitives ──────────────────────────────────

function SectionHeader({ title, onSeeAll, icon }: { title: string; onSeeAll?: () => void; icon?: string }) {
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionTitleRow}>
        {icon && <Text style={styles.sectionIcon}>{icon}</Text>}
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      {onSeeAll && (
        <TouchableOpacity onPress={onSeeAll} accessibilityRole="link">
          <Text style={styles.seeAll}>See all →</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

function AttentionCard({ notification }: { notification: AppNotification }) {
  const router = useRouter();
  const icons: Record<string, string> = {
    verification_requested: '✅',
    case_resolved: '🎉',
    case_assigned: '📋',
    case_in_progress: '🔧',
    duplicate_found: '🔗',
    incident_nearby: '⚠️',
    case_supported: '👍',
    department_requested_info: '❓',
    case_reopened: '🔄',
  };

  return (
    <TouchableOpacity
      style={styles.attentionCard}
      onPress={() => notification.case_id && router.push(`/(app)/case/${notification.case_id}`)}
      accessibilityRole="button"
      accessibilityLabel={notification.title}
    >
      <Text style={styles.attentionIcon}>{icons[notification.type] ?? '📢'}</Text>
      <View style={{ flex: 1 }}>
        <Text style={styles.attentionTitle} numberOfLines={1}>{notification.title}</Text>
        <Text style={styles.attentionBody} numberOfLines={2}>{notification.body}</Text>
      </View>
      {notification.requires_action && (
        <View style={styles.attentionBadge}>
          <Text style={styles.attentionBadgeText}>Action</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

function CaseCard({ item }: { item: CivicCase }) {
  const router = useRouter();
  const statusColor = (Colors.status as any)[item.status] ?? Colors.neutral[400];
  const firstImage = item.evidence?.find(e => e.type === 'image')?.url;

  return (
    <TouchableOpacity
      style={styles.caseCard}
      onPress={() => router.push(`/(app)/case/${item.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`Case ${item.case_number}: ${item.title}`}
    >
      <View style={styles.caseCardContent}>
        {firstImage && (
          <Image source={{ uri: firstImage }} style={styles.caseThumbnail} />
        )}
        <View style={{ flex: 1 }}>
          <View style={styles.caseCardTop}>
            <Text style={styles.caseNumber}>{item.case_number}</Text>
            <View style={[styles.statusBadge, { backgroundColor: statusColor + '18' }]}>
              <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
              <Text style={[styles.statusText, { color: statusColor }]}>{STATUS_LABELS[item.status] ?? item.status}</Text>
            </View>
          </View>
          <Text style={styles.caseTitle} numberOfLines={2}>{item.title}</Text>
          <View style={styles.caseMeta}>
            <Text style={styles.caseMetaText}>
              {CATEGORY_ICONS[item.category] ?? '⚠️'} {item.category}
            </Text>
            {item.location?.landmark && (
              <Text style={styles.caseLandmark} numberOfLines={1}>📍 {item.location.landmark}</Text>
            )}
            <Text style={styles.caseSupporters}>👥 {item.supporter_count}</Text>
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
}

function QuickAction({ icon, label, onPress, badge }: { icon: string; label: string; onPress: () => void; badge?: number }) {
  return (
    <TouchableOpacity
      style={styles.quickAction}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <View style={styles.quickActionIcon}>
        <Text style={styles.quickActionEmoji}>{icon}</Text>
        {badge != null && badge > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{badge > 99 ? '99+' : badge}</Text>
          </View>
        )}
      </View>
      <Text style={styles.quickActionLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

// ─── Main screen ───────────────────────────────────────────

export default function DashboardScreen() {
  const router = useRouter();
  const { user } = useAuthContext();
  const { isOnline, pendingCount } = useOffline();

  const [activeCases, setActiveCases] = useState<CivicCase[]>([]);
  const [awaitingCases, setAwaitingCases] = useState<CivicCase[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
  const [selectedPinCase, setSelectedPinCase] = useState<CivicCase | null>(null);
  const [selectedNews, setSelectedNews] = useState<CivicNewsItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const departments = ['all', 'roads', 'sanitation', 'water', 'lighting'];

  const load = useCallback(async () => {
    try {
      const [activePage, awaitingPage, notifPage] = await Promise.all([
        casesApi.list({ tab: 'active', page_size: 5 }),
        casesApi.list({ tab: 'awaiting_me', page_size: 5 }),
        notificationsApi.list(1),
      ]);
      setActiveCases(activePage.items.length > 0 ? activePage.items : MOCK_CASES.slice(0, 3));
      setAwaitingCases(awaitingPage.items.length > 0 ? awaitingPage.items : MOCK_CASES.filter(c => c.requires_my_action));
      setNotifications(notifPage.items.length > 0 ? notifPage.items.slice(0, 4) : []);
    } catch {
      setActiveCases(MOCK_CASES.slice(0, 3));
      setAwaitingCases(MOCK_CASES.filter(c => c.requires_my_action));
    }
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const allMapCases = activeCases.length > 0 ? activeCases : MOCK_CASES;
  const filteredMapCases = selectedDepartment === 'all'
    ? allMapCases
    : allMapCases.filter(c => c.category === selectedDepartment);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ─── Premium Header ─────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View style={styles.headerLeft}>
            <View style={styles.logoBox}>
              <Text style={styles.logoEmoji}>🏙️</Text>
            </View>
            <View>
              <Text style={styles.subtext}>CIVICCONNECT</Text>
              <Text style={styles.userName}>{user?.name ?? 'Citizen'}</Text>
              <View style={styles.localityBadge}>
                <Text style={styles.localityText}>📍 {user?.locality ?? 'Ranchi, Jharkhand'}</Text>
              </View>
            </View>
          </View>

          <View style={styles.headerRight}>
            <TouchableOpacity
              onPress={() => router.push('/(app)/(tabs)/notifications')}
              style={styles.notifButton}
              accessibilityRole="button"
              accessibilityLabel="Notifications"
            >
              <Text style={styles.notifIcon}>🔔</Text>
              {notifications.some(n => !n.read) && <View style={styles.notifDot} />}
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => router.push('/(app)/(tabs)/profile')}
              style={styles.avatarButton}
            >
              <Image
                source={{ uri: user?.avatar_url ?? 'https://images.pexels.com/photos/771742/pexels-photo-771742.jpeg?auto=compress&cs=tinysrgb&w=100&h=100&fit=crop' }}
                style={styles.avatarImg}
              />
            </TouchableOpacity>
          </View>
        </View>

        {/* ─── Stats Cards in Header ─────────────────────────── */}
        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>📈</Text>
            <Text style={styles.statValue}>{MOCK_STATS.totalIssues}</Text>
            <Text style={styles.statLabel}>TOTAL ISSUES</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>✅</Text>
            <Text style={styles.statValue}>{MOCK_STATS.resolvedIssues}</Text>
            <Text style={styles.statLabel}>RESOLVED</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statIcon}>⏱️</Text>
            <Text style={styles.statValue}>{MOCK_STATS.avgResponseTime}</Text>
            <Text style={styles.statLabel}>AVG RESPONSE</Text>
          </View>
        </View>
      </View>

      {/* Offline indicator */}
      {!isOnline && (
        <View style={styles.offlineStrip}>
          <Text style={styles.offlineText}>
            📶 Offline — {pendingCount > 0 ? `${pendingCount} reports queued` : 'Reports will sync when online'}
          </Text>
        </View>
      )}

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.brand[600]} />}
        showsVerticalScrollIndicator={false}
      >
        {loading ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={Colors.brand[600]} />
            <Text style={styles.loadingText}>Loading your dashboard…</Text>
          </View>
        ) : (
          <>
            {/* ─── Report Issue Hero CTA ────────────────────────── */}
            <View style={styles.heroSection}>
              <TouchableOpacity
                onPress={() => router.push('/(app)/report')}
                style={styles.heroCard}
                accessibilityRole="button"
                accessibilityLabel="Report an Issue"
              >
                <View style={styles.heroIconBox}>
                  <Text style={styles.heroIcon}>📸</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.heroTitle}>Report an Issue</Text>
                  <Text style={styles.heroSubtitle}>Take a photo and report civic problems instantly</Text>
                </View>
                <Text style={styles.heroChevron}>›</Text>
              </TouchableOpacity>
            </View>

            {/* ─── Issues Near You (Interactive Map Section) ────── */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <View style={styles.sectionTitleRow}>
                  <Text style={styles.sectionIcon}>🗺️</Text>
                  <Text style={styles.sectionTitle}>Issues Near You</Text>
                </View>
                <TouchableOpacity onPress={() => router.push('/(app)/map/expanded')}>
                  <Text style={styles.seeAll}>Expand ↗</Text>
                </TouchableOpacity>
              </View>

              {/* Department Filter Pills */}
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.deptFilterRow}
              >
                {departments.map(dept => {
                  const isSelected = selectedDepartment === dept;
                  const icon = dept === 'roads' ? '🛣️' : dept === 'sanitation' ? '🗑️' : dept === 'water' ? '💧' : dept === 'lighting' ? '💡' : '🌐';
                  return (
                    <TouchableOpacity
                      key={dept}
                      onPress={() => {
                        setSelectedDepartment(dept);
                        setSelectedPinCase(null);
                      }}
                      style={[styles.deptPill, isSelected && styles.deptPillActive]}
                    >
                      <Text style={styles.deptPillIcon}>{icon}</Text>
                      <Text style={[styles.deptPillText, isSelected && styles.deptPillTextActive]}>
                        {dept === 'all' ? 'All Issues' : dept.charAt(0).toUpperCase() + dept.slice(1)}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>

              {/* Interactive Map Visual Preview */}
              <View style={styles.mapCanvas}>
                {/* Background Map Graphic Styling */}
                <View style={styles.mapGridPattern}>
                  <View style={styles.mapRoadH} />
                  <View style={[styles.mapRoadH, { top: 120 }]} />
                  <View style={styles.mapRoadV} />
                  <View style={[styles.mapRoadV, { left: 240 }]} />
                  <View style={styles.mapRiver} />
                </View>

                {/* Markers */}
                {filteredMapCases.map((c, idx) => {
                  const isSelected = selectedPinCase?.id === c.id;
                  const statusBg = c.status === 'resolved' ? '#15803D' : c.status === 'in_progress' ? '#D97706' : '#B91C1C';
                  // Stagger pin coordinates realistically on canvas
                  const pinLeft = 40 + ((idx * 65 + 15) % 250);
                  const pinTop = 30 + ((idx * 45 + 20) % 110);

                  return (
                    <TouchableOpacity
                      key={c.id}
                      onPress={() => setSelectedPinCase(c)}
                      style={[
                        styles.mapPin,
                        { left: pinLeft, top: pinTop, backgroundColor: statusBg },
                        isSelected && styles.mapPinSelected,
                      ]}
                      accessibilityLabel={c.title}
                    >
                      <Text style={styles.mapPinEmoji}>{CATEGORY_ICONS[c.category] ?? '📍'}</Text>
                    </TouchableOpacity>
                  );
                })}

                {/* Floating Map Label */}
                <View style={styles.mapBadge}>
                  <Text style={styles.mapBadgeText}>
                    📍 {filteredMapCases.length} nearby issues in Ranchi
                  </Text>
                </View>
              </View>

              {/* Selected Pin Info Card (if tapped) */}
              {selectedPinCase && (
                <View style={styles.pinDetailCard}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.pinDetailTitle} numberOfLines={1}>{selectedPinCase.title}</Text>
                    <Text style={styles.pinDetailSub}>
                      {selectedPinCase.category.toUpperCase()} • Status: {STATUS_LABELS[selectedPinCase.status] ?? selectedPinCase.status}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.pinDetailBtn}
                    onPress={() => router.push(`/(app)/case/${selectedPinCase.id}`)}
                  >
                    <Text style={styles.pinDetailBtnText}>View →</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>

            {/* ─── Attention section ────────────────────────────── */}
            {notifications.length > 0 && (
              <View style={styles.section}>
                <SectionHeader title="Needs your attention" onSeeAll={() => router.push('/(app)/(tabs)/notifications')} />
                {notifications.map(n => <AttentionCard key={n.id} notification={n as any} />)}
              </View>
            )}

            {/* ─── Quick actions ─────────────────────────────────── */}
            <View style={styles.section}>
              <SectionHeader title="Quick actions" />
              <View style={styles.quickActions}>
                <QuickAction icon="📸" label="Report Issue" onPress={() => router.push('/(app)/report')} />
                <QuickAction icon="🗺️" label="Nearby Map" onPress={() => router.push('/(app)/map/expanded')} />
                <QuickAction icon="📋" label="My Cases" onPress={() => router.push('/(app)/(tabs)/my-cases')} badge={awaitingCases.length} />
                <QuickAction icon="🤝" label="Community" onPress={() => router.push('/(app)/(tabs)/community')} />
              </View>
            </View>

            {/* ─── Awaiting my action ────────────────────────────── */}
            {awaitingCases.length > 0 && (
              <View style={styles.section}>
                <SectionHeader title="Awaiting your verification" onSeeAll={() => router.push({ pathname: '/(app)/(tabs)/my-cases', params: { tab: 'awaiting_me' } })} />
                {awaitingCases.map(c => <CaseCard key={c.id} item={c} />)}
              </View>
            )}

            {/* ─── Active cases ──────────────────────────────────── */}
            {activeCases.length > 0 && (
              <View style={styles.section}>
                <SectionHeader title="Your active cases" onSeeAll={() => router.push('/(app)/(tabs)/my-cases')} />
                {activeCases.map(c => <CaseCard key={c.id} item={c} />)}
              </View>
            )}

            {/* ─── Civic News Carousel ──────────────────────────── */}
            <View style={styles.section}>
              <SectionHeader title="Civic News & Bulletins" icon="📰" />
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.newsCarousel}
              >
                {MOCK_NEWS.map(news => (
                  <TouchableOpacity
                    key={news.id}
                    style={styles.newsCard}
                    onPress={() => setSelectedNews(news)}
                    activeOpacity={0.85}
                  >
                    <Image source={{ uri: news.image }} style={styles.newsImage} />
                    <View style={styles.newsContent}>
                      <View style={styles.newsTagRow}>
                        <View style={styles.newsTag}>
                          <Text style={styles.newsTagText}>{news.tag}</Text>
                        </View>
                        <Text style={styles.newsDate}>{news.date}</Text>
                      </View>
                      <Text style={styles.newsTitle} numberOfLines={2}>{news.title}</Text>
                      <Text style={styles.newsDesc} numberOfLines={2}>{news.description}</Text>
                    </View>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </>
        )}
      </ScrollView>

      {/* ─── Civic News Bulletin Modal ────────────────────── */}
      <Modal
        visible={!!selectedNews}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedNews(null)}
      >
        <View style={styles.newsModalBackdrop}>
          <View style={styles.newsModalContent}>
            {selectedNews && (
              <>
                <Image source={{ uri: selectedNews.image }} style={styles.newsModalImg} resizeMode="cover" />
                <View style={styles.newsModalBody}>
                  <View style={styles.newsTagRow}>
                    <View style={styles.newsTag}>
                      <Text style={styles.newsTagText}>{selectedNews.tag}</Text>
                    </View>
                    <Text style={styles.newsDate}>{selectedNews.date}</Text>
                  </View>
                  <Text style={styles.newsModalTitle}>{selectedNews.title}</Text>
                  <Text style={styles.newsModalDesc}>{selectedNews.description}</Text>
                  <TouchableOpacity
                    style={styles.newsModalCloseBtn}
                    onPress={() => setSelectedNews(null)}
                  >
                    <Text style={styles.newsModalCloseText}>Close Bulletin</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAF9' },
  header: {
    backgroundColor: '#0D4A1A',
    paddingHorizontal: Spacing[5],
    paddingTop: Spacing[4],
    paddingBottom: Spacing[5],
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[4],
  },
  headerLeft: {
    flexDirection: 'row',
    gap: Spacing[3],
    alignItems: 'center',
  },
  logoBox: {
    width: 44,
    height: 44,
    borderRadius: Radii.lg,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
  },
  logoEmoji: { fontSize: 24 },
  subtext: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 10,
    fontWeight: Typography.bold,
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  userName: {
    color: '#fff',
    fontSize: Typography.lg,
    fontWeight: Typography.extrabold,
    letterSpacing: -0.3,
  },
  localityBadge: {
    marginTop: 2,
  },
  localityText: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 11,
    fontWeight: Typography.medium,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[2.5],
  },
  notifButton: {
    width: 38,
    height: 38,
    borderRadius: Radii.md,
    backgroundColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  notifIcon: { fontSize: 18 },
  notifDot: {
    position: 'absolute',
    top: 7,
    right: 7,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.error,
    borderWidth: 1.5,
    borderColor: '#0D4A1A',
  },
  avatarButton: {
    width: 38,
    height: 38,
    borderRadius: Radii.md,
    overflow: 'hidden',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  avatarImg: { width: '100%', height: '100%' },

  // Stats row
  statsRow: {
    flexDirection: 'row',
    gap: Spacing[2.5],
  },
  statCard: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: Radii.lg,
    paddingVertical: Spacing[3],
    paddingHorizontal: Spacing[2],
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  statIcon: { fontSize: 16, marginBottom: 2 },
  statValue: {
    color: '#fff',
    fontSize: Typography.base,
    fontWeight: Typography.extrabold,
    letterSpacing: -0.3,
  },
  statLabel: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 9,
    fontWeight: Typography.bold,
    marginTop: 2,
    letterSpacing: 0.5,
  },

  offlineStrip: {
    backgroundColor: Colors.warning,
    paddingVertical: Spacing[2],
    paddingHorizontal: Spacing[4],
  },
  offlineText: {
    color: '#fff',
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    textAlign: 'center',
  },
  scrollContent: {
    paddingBottom: Layout.bottomNavHeight + Spacing[6],
  },

  // Hero Report Card
  heroSection: {
    paddingHorizontal: Spacing[5],
    marginTop: Spacing[4],
  },
  heroCard: {
    backgroundColor: '#fff',
    borderRadius: Radii['2xl'],
    padding: Spacing[4],
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3.5],
    borderWidth: 1.5,
    borderColor: '#D1FAE5',
    ...Shadows.md,
  },
  heroIconBox: {
    width: 50,
    height: 50,
    borderRadius: Radii.xl,
    backgroundColor: '#10B981',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroIcon: { fontSize: 26 },
  heroTitle: {
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
  },
  heroSubtitle: {
    fontSize: Typography.xs,
    color: Colors.neutral[500],
    marginTop: 2,
  },
  heroChevron: {
    fontSize: 26,
    color: '#10B981',
    fontWeight: 'bold',
  },

  section: {
    paddingHorizontal: Spacing[5],
    marginTop: Spacing[5],
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing[3],
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[1.5],
  },
  sectionIcon: { fontSize: 18 },
  sectionTitle: {
    fontSize: Typography.base,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
  },
  seeAll: {
    fontSize: Typography.sm,
    color: '#10B981',
    fontWeight: Typography.bold,
  },

  // Dept Filter Pills
  deptFilterRow: {
    gap: Spacing[2],
    paddingBottom: Spacing[2.5],
  },
  deptPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[2],
    borderRadius: Radii.full,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: Colors.neutral[200],
  },
  deptPillActive: {
    backgroundColor: '#10B981',
    borderColor: '#10B981',
  },
  deptPillIcon: { fontSize: 14 },
  deptPillText: {
    fontSize: Typography.xs,
    fontWeight: Typography.semibold,
    color: Colors.neutral[600],
  },
  deptPillTextActive: { color: '#fff' },

  // Map Canvas
  mapCanvas: {
    height: 180,
    backgroundColor: '#E2E8F0',
    borderRadius: Radii.xl,
    overflow: 'hidden',
    position: 'relative',
    borderWidth: 1,
    borderColor: Colors.neutral[300],
  },
  mapGridPattern: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#E6EFE9',
  },
  mapRoadH: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 60,
    height: 14,
    backgroundColor: '#CBD5E1',
  },
  mapRoadV: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 110,
    width: 14,
    backgroundColor: '#CBD5E1',
  },
  mapRiver: {
    position: 'absolute',
    top: 140,
    left: 0,
    right: 0,
    height: 20,
    backgroundColor: '#BAE6FD',
  },
  mapPin: {
    position: 'absolute',
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
    ...Shadows.md,
  },
  mapPinSelected: {
    transform: [{ scale: 1.3 }],
    borderColor: '#FEF08A',
  },
  mapPinEmoji: { fontSize: 16 },
  mapBadge: {
    position: 'absolute',
    bottom: 8,
    left: 10,
    backgroundColor: 'rgba(15, 23, 42, 0.75)',
    paddingHorizontal: Spacing[2.5],
    paddingVertical: 4,
    borderRadius: Radii.md,
  },
  mapBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: Typography.semibold,
  },

  // Pin detail popup
  pinDetailCard: {
    marginTop: Spacing[2],
    backgroundColor: '#fff',
    borderRadius: Radii.lg,
    padding: Spacing[3],
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.neutral[200],
    ...Shadows.sm,
  },
  pinDetailTitle: {
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
  },
  pinDetailSub: {
    fontSize: 10,
    color: Colors.neutral[500],
    marginTop: 2,
  },
  pinDetailBtn: {
    backgroundColor: '#10B981',
    borderRadius: Radii.md,
    paddingHorizontal: Spacing[3],
    paddingVertical: Spacing[1.5],
  },
  pinDetailBtnText: {
    color: '#fff',
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
  },

  attentionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: Radii.lg,
    padding: Spacing[4],
    marginBottom: Spacing[2],
    gap: Spacing[3],
    borderWidth: 1,
    borderColor: Colors.neutral[100],
    ...Shadows.sm,
  },
  attentionIcon: { fontSize: 24 },
  attentionTitle: {
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    marginBottom: 2,
  },
  attentionBody: { fontSize: Typography.xs, color: Colors.neutral[500], lineHeight: 16 },
  attentionBadge: {
    backgroundColor: Colors.brand[600],
    borderRadius: Radii.full,
    paddingHorizontal: Spacing[2],
    paddingVertical: 2,
  },
  attentionBadgeText: { fontSize: 10, color: '#fff', fontWeight: Typography.bold },

  quickActions: { flexDirection: 'row', justifyContent: 'space-between' },
  quickAction: { alignItems: 'center', flex: 1, paddingVertical: Spacing[2] },
  quickActionIcon: {
    width: 52,
    height: 52,
    borderRadius: Radii.xl,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing[1.5],
    ...Shadows.sm,
    borderWidth: 1,
    borderColor: Colors.neutral[100],
    position: 'relative',
  },
  quickActionEmoji: { fontSize: 24 },
  quickActionLabel: { fontSize: 11, color: Colors.neutral[600], fontWeight: Typography.medium, textAlign: 'center' },
  badge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: Colors.error,
    borderRadius: Radii.full,
    minWidth: 18,
    height: 18,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 3,
    borderWidth: 2,
    borderColor: '#fff',
  },
  badgeText: { fontSize: 10, color: '#fff', fontWeight: Typography.bold },

  // Case card
  caseCard: {
    backgroundColor: '#fff',
    borderRadius: Radii.xl,
    padding: Spacing[3.5],
    marginBottom: Spacing[2.5],
    ...Shadows.sm,
    borderWidth: 1,
    borderColor: Colors.neutral[100],
  },
  caseCardContent: {
    flexDirection: 'row',
    gap: Spacing[3],
    alignItems: 'center',
  },
  caseThumbnail: {
    width: 64,
    height: 64,
    borderRadius: Radii.lg,
  },
  caseCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  caseNumber: { fontSize: 11, fontWeight: Typography.bold, color: Colors.neutral[400], letterSpacing: 0.5 },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: Spacing[2], paddingVertical: 2, borderRadius: Radii.full },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 10, fontWeight: Typography.bold },
  caseTitle: { fontSize: Typography.sm, fontWeight: Typography.bold, color: Colors.neutral[900], marginBottom: 4, lineHeight: 18 },
  caseMeta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  caseMetaText: { fontSize: 11, color: Colors.neutral[500], textTransform: 'capitalize' },
  caseLandmark: { fontSize: 11, color: Colors.neutral[400], maxWidth: 120 },
  caseSupporters: { fontSize: 11, color: Colors.neutral[500], fontWeight: Typography.medium },

  // Civic News Carousel
  newsCarousel: {
    gap: Spacing[3],
    paddingBottom: Spacing[2],
  },
  newsCard: {
    width: 250,
    backgroundColor: '#fff',
    borderRadius: Radii.xl,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.neutral[100],
    ...Shadows.sm,
  },
  newsImage: {
    width: '100%',
    height: 120,
    backgroundColor: '#E2E8F0',
  },
  newsContent: {
    padding: Spacing[3],
  },
  newsTagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  newsTag: {
    backgroundColor: '#ECFDF5',
    paddingHorizontal: Spacing[2],
    paddingVertical: 2,
    borderRadius: Radii.sm,
  },
  newsTagText: {
    fontSize: 9,
    fontWeight: Typography.bold,
    color: '#059669',
  },
  newsDate: {
    fontSize: 10,
    color: Colors.neutral[400],
  },
  newsTitle: {
    fontSize: Typography.xs,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    lineHeight: 16,
    marginBottom: 4,
  },
  newsDesc: {
    fontSize: 11,
    color: Colors.neutral[500],
    lineHeight: 15,
  },

  loadingBox: { alignItems: 'center', paddingTop: Spacing[16], gap: Spacing[4] },
  loadingText: { color: Colors.neutral[400], fontSize: Typography.base },

  newsModalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing[5],
  },
  newsModalContent: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: '#FFFFFF',
    borderRadius: Radii.xl,
    overflow: 'hidden',
    ...Shadows.lg,
  },
  newsModalImg: {
    width: '100%',
    height: 180,
    backgroundColor: '#E2E8F0',
  },
  newsModalBody: {
    padding: Spacing[5],
    gap: Spacing[3],
  },
  newsModalTitle: {
    fontSize: Typography.lg,
    fontWeight: Typography.bold,
    color: Colors.neutral[900],
    lineHeight: 24,
  },
  newsModalDesc: {
    fontSize: Typography.sm,
    color: Colors.neutral[600],
    lineHeight: 22,
  },
  newsModalCloseBtn: {
    backgroundColor: Colors.brand[600],
    borderRadius: Radii.lg,
    paddingVertical: Spacing[3],
    alignItems: 'center',
    marginTop: Spacing[2],
  },
  newsModalCloseText: {
    color: '#FFFFFF',
    fontSize: Typography.sm,
    fontWeight: Typography.bold,
  },
});
