/**
 * HSAAI Mobile — Task Center Screen (Phase 11)
 * =============================================
 * Centralized view of all tasks assigned to or created by the user.
 * Includes AI agent tasks, workflow tasks, and approval requests.
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
// FIX F-05: client is a default export.
import client from '../../api/client';

const COLORS = {
  primary: '#2a6887', success: '#44925e', warning: '#a4864a',
  danger: '#ac574f', bg: '#0a0a0a', surface: '#1a1a1a',
  text: '#ffffff', textMuted: '#999999',
};

const PRIORITY_COLORS = {
  low: COLORS.success, medium: COLORS.warning,
  high: COLORS.danger, critical: COLORS.danger,
};

export default function TaskCenterScreen() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'pending' | 'in_progress' | 'completed'>('all');

  const fetchTasks = async () => {
    try {
      const response = await client.get('/v1/tasks', { params: { status: filter } });
      setTasks(response.data.tasks || []);
    } catch (err) {
      // Fallback to empty
      setTasks([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchTasks(); }, [filter]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchTasks();
  };

  const renderTask = ({ item }: { item: any }) => (
    <TouchableOpacity style={styles.taskCard} onPress={() => {/* navigate to detail */}}>
      <View style={styles.taskHeader}>
        <View style={[styles.priorityBadge, { backgroundColor: PRIORITY_COLORS[item.priority] || COLORS.textMuted }]}>
          <Text style={styles.priorityText}>{t(`priority.${item.priority}`)}</Text>
        </View>
        <Text style={styles.taskType}>{t(`taskType.${item.type}`)}</Text>
      </View>
      <Text style={styles.taskTitle}>{item.title}</Text>
      <Text style={styles.taskDescription} numberOfLines={2}>{item.description}</Text>
      <View style={styles.taskFooter}>
        <Ionicons name="time-outline" size={14} color={COLORS.textMuted} />
        <Text style={styles.taskMeta}>
          {item.due_date ? new Date(item.due_date).toLocaleDateString() : t('tasks.noDueDate')}
        </Text>
        <Ionicons name="person-outline" size={14} color={COLORS.textMuted} style={{ marginLeft: 12 }} />
        <Text style={styles.taskMeta}>{item.assigned_to || t('tasks.unassigned')}</Text>
      </View>
    </TouchableOpacity>
  );

  const filters = ['all', 'pending', 'in_progress', 'completed'] as const;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t('tasks.title')}</Text>

      <View style={styles.filterRow}>
        {filters.map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.filterButton, filter === f && styles.filterButtonActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {t(`tasks.${f}`)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={tasks}
          renderItem={renderTask}
          keyExtractor={item => item.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          contentContainerStyle={{ paddingBottom: 20 }}
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Ionicons name="checkmark-done-circle" size={64} color={COLORS.textMuted} />
              <Text style={styles.emptyText}>{t('tasks.empty')}</Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  title: { color: COLORS.text, fontSize: 24, fontWeight: 'bold', padding: 20 },
  filterRow: { flexDirection: 'row', paddingHorizontal: 20, marginBottom: 12 },
  filterButton: {
    flex: 1, paddingVertical: 8, marginHorizontal: 4, borderRadius: 8,
    backgroundColor: COLORS.surface, alignItems: 'center',
  },
  filterButtonActive: { backgroundColor: COLORS.primary },
  filterText: { color: COLORS.textMuted, fontSize: 12 },
  filterTextActive: { color: 'white', fontWeight: 'bold' },
  taskCard: {
    backgroundColor: COLORS.surface, borderRadius: 12, padding: 16,
    marginHorizontal: 20, marginBottom: 12,
  },
  taskHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  priorityBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4 },
  priorityText: { color: 'white', fontSize: 10, fontWeight: 'bold' },
  taskType: { color: COLORS.textMuted, fontSize: 12 },
  taskTitle: { color: COLORS.text, fontSize: 16, fontWeight: 'bold', marginBottom: 4 },
  taskDescription: { color: COLORS.textMuted, fontSize: 14, marginBottom: 12 },
  taskFooter: { flexDirection: 'row', alignItems: 'center' },
  taskMeta: { color: COLORS.textMuted, fontSize: 12, marginLeft: 4 },
  emptyState: { alignItems: 'center', marginTop: 60 },
  emptyText: { color: COLORS.textMuted, marginTop: 16, fontSize: 16 },
});
