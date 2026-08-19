import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { HSAHeader, KPICard } from '@components/index';
import { getDashboard, type DashboardData, type ServiceStatus } from '@api/dashboard';
import { useAuthStore } from '@store/authStore';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';

export function DashboardScreen() {
  const { user } = useAuthStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const dashboard = await getDashboard();
      setData(dashboard);
    } catch (err) {
      setError('تعذر تحميل البيانات. تأكد من الاتصال بالشبكة الداخلية.');
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <HSAHeader
        title="لوحة التحكم"
        subtitle={user?.displayName || 'مرحباً بك'}
      />
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.hsaYellow} />}
      >
        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity onPress={loadData} style={styles.retryButton}>
              <Text style={styles.retryText}>إعادة المحاولة</Text>
            </TouchableOpacity>
          </View>
        )}

        {data && (
          <>
            {/* KPI Cards */}
            <View style={styles.kpiRow}>
              {data.kpis.slice(0, 2).map((kpi, i) => (
                <KPICard key={i} {...kpi} />
              ))}
            </View>
            <View style={styles.kpiRow}>
              {data.kpis.slice(2, 4).map((kpi, i) => (
                <KPICard key={i + 2} {...kpi} />
              ))}
            </View>

            {/* Weekly Usage Chart */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>استخدام AI — آخر 7 أيام</Text>
              <View style={styles.chartContainer}>
                {data.weeklyUsage.map((item, i) => {
                  const maxVal = Math.max(...data.weeklyUsage.map(d => d.value));
                  const height = maxVal > 0 ? (item.value / maxVal) * 120 : 0;
                  return (
                    <View key={i} style={styles.barColumn}>
                      <View style={styles.barValueContainer}>
                        <Text style={styles.barValue}>{(item.value / 1000).toFixed(1)}K</Text>
                      </View>
                      <View style={[styles.bar, { height }]} />
                      <Text style={styles.barLabel}>{item.day}</Text>
                    </View>
                  );
                })}
              </View>
            </View>

            {/* Services Status */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>حالة الخدمات</Text>
              {data.services.map((svc, i) => (
                <ServiceRow key={i} service={svc} />
              ))}
            </View>

            {/* Department Adoption */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>اعتماد الأقسام</Text>
              {data.departmentAdoption.map((dept, i) => (
                <View key={i} style={styles.adoptionRow}>
                  <Text style={styles.adoptionLabel}>{dept.department}</Text>
                  <View style={styles.adoptionBarBg}>
                    <View style={[styles.adoptionBarFill, { width: `${dept.percentage}%` }]} />
                  </View>
                  <Text style={styles.adoptionValue}>{dept.percentage}%</Text>
                </View>
              ))}
            </View>
          </>
        )}

        {!data && !error && (
          <View style={styles.loadingContainer}>
            <Text style={styles.loadingText}>جارٍ تحميل البيانات...</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function ServiceRow({ service }: { service: ServiceStatus }) {
  const statusColor =
    service.status === 'healthy' ? colors.success :
    service.status === 'warning' ? colors.warning :
    colors.error;
  const statusText =
    service.status === 'healthy' ? 'صحي' :
    service.status === 'warning' ? 'تحذير' :
    'متوقف';

  return (
    <View style={styles.serviceRow}>
      <View style={[styles.serviceDot, { backgroundColor: statusColor }]} />
      <Text style={styles.serviceName}>{service.name}</Text>
      <Text style={styles.servicePort}>{service.port}</Text>
      <Text style={styles.serviceLatency}>{service.latencyMs}ms</Text>
      <View style={[styles.serviceStatusBadge, { backgroundColor: `${statusColor}20` }]}>
        <Text style={[styles.serviceStatusText, { color: statusColor }]}>{statusText}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scrollView: { flex: 1 },
  scrollContent: { padding: spacing.lg, paddingBottom: 80 },
  kpiRow: { flexDirection: 'row', marginBottom: spacing.sm },
  section: { marginTop: spacing.xl },
  sectionTitle: {
    ...typography.h4,
    color: colors.textWhite,
    marginBottom: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  chartContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 160,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  barColumn: {
    flex: 1,
    alignItems: 'center',
    marginHorizontal: 2,
  },
  barValueContainer: { marginBottom: 4 },
  barValue: { ...typography.caption, color: colors.textLight, fontSize: 9 },
  bar: {
    width: 20,
    backgroundColor: colors.hsaYellow,
    borderRadius: 4,
    minHeight: 4,
  },
  barLabel: { ...typography.caption, color: colors.textLight, fontSize: 9, marginTop: 4 },
  serviceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  serviceDot: { width: 8, height: 8, borderRadius: 4, marginLeft: spacing.sm },
  serviceName: { ...typography.bodySmall, color: colors.textWhite, flex: 1 },
  servicePort: { ...typography.caption, color: colors.textLight, fontFamily: 'monospace' },
  serviceLatency: { ...typography.caption, color: colors.textLight, marginHorizontal: spacing.sm },
  serviceStatusBadge: {
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  serviceStatusText: { ...typography.caption, fontWeight: '700' },
  adoptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  adoptionLabel: { ...typography.bodySmall, color: colors.textWhite, width: 100 },
  adoptionBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: colors.surfaceLight,
    borderRadius: 4,
    marginHorizontal: spacing.sm,
  },
  adoptionBarFill: {
    height: '100%',
    backgroundColor: colors.hsaYellow,
    borderRadius: 4,
  },
  adoptionValue: { ...typography.caption, color: colors.hsaYellow, fontWeight: '700', width: 40 },
  errorContainer: { alignItems: 'center', padding: spacing.xl },
  errorText: { ...typography.body, color: colors.error, textAlign: 'center', marginBottom: spacing.md },
  retryButton: {
    backgroundColor: colors.hsaYellow,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
  },
  retryText: { ...typography.button, color: colors.hsaBlack },
  loadingContainer: { alignItems: 'center', padding: spacing.xxxl },
  loadingText: { ...typography.body, color: colors.textLight },
});
