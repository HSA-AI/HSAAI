import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';
import type { Approval } from '@api/governance';

interface ApprovalCardProps {
  approval: Approval;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

const TYPE_ICONS: Record<Approval['type'], string> = {
  model_deployment: 'rocket-launch',
  data_access: 'database',
  agent_creation: 'robot',
  workflow_change: 'file-tree',
};

const RISK_COLORS: Record<Approval['riskLevel'], string> = {
  low: colors.success,
  medium: colors.warning,
  high: colors.error,
  critical: '#7C2D12',
};

export function ApprovalCard({ approval, onApprove, onReject }: ApprovalCardProps) {
  const icon = TYPE_ICONS[approval.type] || 'clipboard-text';
  const riskColor = RISK_COLORS[approval.riskLevel];

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={[styles.iconContainer, { backgroundColor: `${riskColor}20` }]}>
          <Icon name={icon} size={24} color={riskColor} />
        </View>
        <View style={styles.headerContent}>
          <Text style={styles.title} numberOfLines={2}>{approval.title}</Text>
          <Text style={styles.requestedBy}>طلب: {approval.requestedBy}</Text>
        </View>
        <View style={[styles.riskBadge, { backgroundColor: `${riskColor}20` }]}>
          <Text style={[styles.riskText, { color: riskColor }]}>
            {approval.riskLevel.toUpperCase()}
          </Text>
        </View>
      </View>

      <Text style={styles.description} numberOfLines={3}>{approval.description}</Text>

      <View style={styles.metaRow}>
        <Text style={styles.metaText}>⏱ {new Date(approval.requestedAt).toLocaleDateString('ar')}</Text>
        <Text style={styles.metaText}>👥 {approval.approvers.length} معتمد</Text>
      </View>

      {approval.status === 'pending' && (
        <View style={styles.actionsRow}>
          <TouchableOpacity
            style={[styles.actionButton, styles.approveButton]}
            onPress={() => onApprove(approval.id)}
          >
            <Icon name="check" size={18} color={colors.success} />
            <Text style={styles.approveText}>اعتماد</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, styles.rejectButton]}
            onPress={() => onReject(approval.id)}
          >
            <Icon name="close" size={18} color={colors.error} />
            <Text style={styles.rejectText}>رفض</Text>
          </TouchableOpacity>
        </View>
      )}

      {approval.status !== 'pending' && (
        <View style={[styles.statusBadge,
          { backgroundColor: approval.status === 'approved' ? colors.successBg : colors.errorBg }
        ]}>
          <Text style={[styles.statusText,
            { color: approval.status === 'approved' ? colors.success : colors.error }
          ]}>
            {approval.status === 'approved' ? '✓ معتمد' : '✗ مرفوض'}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderRightWidth: 4,
    borderRightColor: colors.hsaYellow,
    ...shadows.small,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: spacing.sm,
  },
  headerContent: {
    flex: 1,
  },
  title: {
    ...typography.h4,
    color: colors.textPrimary,
    marginBottom: 2,
  },
  requestedBy: {
    ...typography.caption,
    color: colors.textLight,
  },
  riskBadge: {
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  riskText: {
    ...typography.overline,
    fontWeight: '800',
  },
  description: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    gap: spacing.lg,
    marginTop: spacing.sm,
  },
  metaText: {
    ...typography.caption,
    color: colors.textLight,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.sm + 2,
    borderRadius: radius.md,
    gap: spacing.xs,
  },
  approveButton: {
    backgroundColor: colors.successBg,
    borderWidth: 1,
    borderColor: colors.success,
  },
  rejectButton: {
    backgroundColor: colors.errorBg,
    borderWidth: 1,
    borderColor: colors.error,
  },
  approveText: {
    ...typography.buttonSmall,
    color: colors.success,
  },
  rejectText: {
    ...typography.buttonSmall,
    color: colors.error,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginTop: spacing.sm,
  },
  statusText: {
    ...typography.buttonSmall,
    fontWeight: '700',
  },
});
