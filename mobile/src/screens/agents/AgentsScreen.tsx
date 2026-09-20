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
import { HSAHeader, AgentCard } from '@components/index';
import { getAgents, type Agent } from '@api/agents';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius } from '@theme/spacing';

export function AgentsScreen() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      setError(null);
      const data = await getAgents();
      setAgents(data);
    } catch {
      setError('تعذر تحميل الوكلاء. تأكد من الاتصال بالشبكة.');
    }
  }, []);

  React.useEffect(() => { loadAgents(); }, [loadAgents]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadAgents();
    setRefreshing(false);
  };

  const handleAgentPress = (agent: Agent) => {
    // Navigate to chat with this agent
    // For now, just show an alert
    console.log('Agent selected:', agent.name);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <HSAHeader title="الوكلاء الذكيون" subtitle={`${agents.length} وكيل متاح`} />
      <FlatList
        data={agents}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <AgentCard agent={item} onPress={handleAgentPress} />
        )}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.hsaYellow} />}
        ListEmptyComponent={
          error ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>{error}</Text>
              <TouchableOpacity onPress={loadAgents} style={styles.retryButton}>
                <Text style={styles.retryText}>إعادة المحاولة</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>لا توجد وكلاء متاحون</Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: spacing.lg, paddingBottom: 80 },
  emptyContainer: { alignItems: 'center', padding: spacing.xxxl },
  emptyText: { ...typography.body, color: colors.textLight, textAlign: 'center', marginBottom: spacing.md },
  retryButton: {
    backgroundColor: colors.hsaYellow,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
  },
  retryText: { ...typography.button, color: colors.hsaBlack },
});
