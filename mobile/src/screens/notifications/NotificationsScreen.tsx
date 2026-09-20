import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { HSAHeader } from '@components/index';
import { getNotifications, markAsRead, markAllAsRead, type AppNotification } from '@api/notifications';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius } from '@theme/spacing';

const NOTIF_ICONS: Record<string, string> = {
  approval: 'clipboard-check',
  alert: 'alert',
  info: 'information',
  security: 'shield-alert',
  system: 'cog',
};

const PRIORITY_COLORS: Record<string, string> = {
  low: colors.info,
  medium: colors.warning,
  high: colors.error,
  critical: '#7C2D12',
};

export function NotificationsScreen() {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadNotifications = useCallback(async () => {
    try {
      setError(null);
      const data = await getNotifications();
      setNotifications(data);
    } catch {
      setError('تعذر تحميل الإشعارات.');
    }
  }, []);

  React.useEffect(() => { loadNotifications(); }, [loadNotifications]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadNotifications();
    setRefreshing(false);
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch {}
  };

  const handlePress = async (notif: AppNotification) => {
    if (!notif.read) {
      try {
        await markAsRead(notif.id);
        setNotifications(prev =>
          prev.map(n => n.id === notif.id ? { ...n, read: true } : n)
        );
      } catch {}
    }
  };

  const renderNotification = ({ item }: { item: AppNotification }) => {
    const icon = NOTIF_ICONS[item.type] || 'bell';
    const priorityColor = PRIORITY_COLORS[item.priority] || colors.textLight;
    return (
      <TouchableOpacity
        style={[styles.notifCard, !item.read && styles.unreadCard]}
        onPress={() => handlePress(item)}
        activeOpacity={0.8}
      >
        <View style={[styles.notifIcon, { backgroundColor: `${priorityColor}20` }]}>
          <Icon name={icon} size={22} color={priorityColor} />
        </View>
        <View style={styles.notifContent}>
          <View style={styles.notifHeader}>
            <Text style={styles.notifTitle} numberOfLines={1}>{item.title}</Text>
            {!item.read && <View style={styles.unreadDot} />}
          </View>
          <Text style={styles.notifBody} numberOfLines={2}>{item.body}</Text>
          <Text style={styles.notifTime}>{item.createdAt}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <HSAHeader
        title="الإشعارات"
        subtitle={unreadCount > 0 ? `${unreadCount} غير مقروء` : 'الكل مقروء'}
        rightAction={
          unreadCount > 0 ? (
            <TouchableOpacity onPress={handleMarkAllRead} style={styles.markAllButton}>
              <Text style={styles.markAllText}>تعليم الكل</Text>
            </TouchableOpacity>
          ) : null
        }
      />
      <FlatList
        data={notifications}
        keyExtractor={(item) => item.id}
        renderItem={renderNotification}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.hsaYellow} />}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="bell-off-outline" size={48} color={colors.textLight} />
            <Text style={styles.emptyText}>لا توجد إشعارات</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: spacing.lg, paddingBottom: 80 },
  markAllButton: { padding: spacing.xs },
  markAllText: { ...typography.caption, color: colors.hsaYellow, fontWeight: '700' },
  notifCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  unreadCard: {
    borderRightWidth: 3,
    borderRightColor: colors.hsaYellow,
  },
  notifIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: spacing.sm,
  },
  notifContent: { flex: 1 },
  notifHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  notifTitle: {
    ...typography.h4,
    color: colors.textWhite,
    flex: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.hsaYellow,
    marginLeft: spacing.sm,
  },
  notifBody: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: 4,
  },
  notifTime: {
    ...typography.caption,
    color: colors.textLight,
    marginTop: 4,
  },
  emptyContainer: { alignItems: 'center', padding: spacing.xxxl },
  emptyText: { ...typography.body, color: colors.textLight, marginTop: spacing.md },
});
