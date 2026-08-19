import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';
import type { Agent } from '@api/agents';

interface AgentCardProps {
  agent: Agent;
  onPress: (agent: Agent) => void;
}

const AGENT_ICONS: Record<string, string> = {
  'HR Assistant': 'account-tie',
  'Finance Agent': 'currency-usd',
  'Legal Advisor': 'gavel',
  'Operations Agent': 'cog',
  'Research Agent': 'magnify',
  'Code Assistant': 'code-braces',
};

export function AgentCard({ agent, onPress }: AgentCardProps) {
  const iconName = AGENT_ICONS[agent.name] || 'robot';
  const statusColor =
    agent.status === 'active' ? colors.online :
    agent.status === 'idle' ? colors.pending :
    colors.offline;

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(agent)}
      activeOpacity={0.8}
    >
      <View style={[styles.iconContainer, { backgroundColor: colors.hsaSoft }]}>
        <Icon name={iconName} size={28} color={colors.hsaGold} />
      </View>
      <View style={styles.content}>
        <View style={styles.headerRow}>
          <Text style={styles.name}>{agent.nameAr || agent.name}</Text>
          <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
        </View>
        <Text style={styles.description} numberOfLines={2}>{agent.description}</Text>
        <View style={styles.toolsRow}>
          {agent.tools.slice(0, 3).map((tool, i) => (
            <View key={i} style={styles.toolBadge}>
              <Text style={styles.toolText}>{tool}</Text>
            </View>
          ))}
          {agent.tools.length > 3 && (
            <Text style={styles.moreText}>+{agent.tools.length - 3}</Text>
          )}
        </View>
        {agent.totalRequests !== undefined && (
          <Text style={styles.metrics}>
            {agent.totalRequests.toLocaleString()} طلب · {agent.successRate || 0}% نجاح
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadows.small,
  },
  iconContainer: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: spacing.sm,
  },
  content: {
    flex: 1,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  name: {
    ...typography.h4,
    color: colors.textPrimary,
    flex: 1,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  description: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  toolsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  toolBadge: {
    backgroundColor: colors.divider,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  toolText: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  moreText: {
    ...typography.caption,
    color: colors.textLight,
    alignSelf: 'center',
  },
  metrics: {
    ...typography.caption,
    color: colors.textLight,
    marginTop: spacing.xs,
  },
});
