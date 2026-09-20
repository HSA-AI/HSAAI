import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { HSAHeader, ApprovalCard } from '@components/index';
import { getPendingApprovals, approveRequest, rejectRequest, type Approval } from '@api/governance';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius } from '@theme/spacing';

export function ApprovalsScreen() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadApprovals = useCallback(async () => {
    try {
      setError(null);
      const data = await getPendingApprovals();
      setApprovals(data);
    } catch {
      setError('تعذر تحميل الطلبات. تأكد من الاتصال بالشبكة.');
    }
  }, []);

  React.useEffect(() => { loadApprovals(); }, [loadApprovals]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadApprovals();
    setRefreshing(false);
  };

  const handleApprove = async (id: string) => {
    Alert.alert(
      'تأكيد الاعتماد',
      'هل أنت متأكد من اعتماد هذا الطلب؟',
      [
        { text: 'إلغاء', style: 'cancel' },
        {
          text: 'اعتماد',
          onPress: async () => {
            try {
              await approveRequest(id);
              setApprovals(prev => prev.filter(a => a.id !== id));
              Alert.alert('✓ تم', 'تم اعتماد الطلب بنجاح');
            } catch {
              Alert.alert('✗ خطأ', 'فشل اعتماد الطلب');
            }
          },
        },
      ],
    );
  };

  const handleReject = async (id: string) => {
    Alert.prompt(
      'سبب الرفض',
      'يرجى ذكر سبب رفض الطلب:',
      async (reason) => {
        if (!reason) return;
        try {
          await rejectRequest(id, reason);
          setApprovals(prev => prev.filter(a => a.id !== id));
          Alert.alert('✓ تم', 'تم رفض الطلب');
        } catch {
          Alert.alert('✗ خطأ', 'فشل رفض الطلب');
        }
      },
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <HSAHeader title="الموافقات والحوكمة" subtitle={`${approvals.length} طلب بانتظار`} />
      <FlatList
        data={approvals}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ApprovalCard
            approval={item}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.hsaYellow} />}
        ListEmptyComponent={
          error ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>{error}</Text>
            </View>
          ) : (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>✓</Text>
              <Text style={styles.emptyText}>لا توجد طلبات بانتظار الموافقة</Text>
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
  emptyIcon: { fontSize: 48, color: colors.success, marginBottom: spacing.md },
  emptyText: { ...typography.body, color: colors.textLight, textAlign: 'center' },
});
