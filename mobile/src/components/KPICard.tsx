import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';

interface KPICardProps {
  label: string;
  value: string;
  change?: string;
  trend?: 'up' | 'down' | 'stable';
  color?: string;
}

export function KPICard({ label, value, change, trend, color }: KPICardProps) {
  const trendColor = trend === 'up' ? colors.success : trend === 'down' ? colors.error : colors.textLight;
  const trendIcon = trend === 'up' ? '▲' : trend === 'down' ? '▼' : '●';

  return (
    <View style={styles.card}>
      <Text style={styles.label} numberOfLines={1}>{label}</Text>
      <Text style={[styles.value, { color: color || colors.hsaYellow }]}>{value}</Text>
      {change && (
        <Text style={[styles.change, { color: trendColor }]}>
          {trendIcon} {change}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    flex: 1,
    marginHorizontal: spacing.xs,
    borderLeftWidth: 3,
    borderLeftColor: colors.hsaYellow,
    ...shadows.small,
  },
  label: {
    ...typography.kpiLabel,
    color: colors.textLight,
    marginBottom: spacing.xs,
  },
  value: {
    ...typography.kpiValue,
    marginBottom: spacing.xs,
  },
  change: {
    ...typography.caption,
    fontWeight: '600',
  },
});
