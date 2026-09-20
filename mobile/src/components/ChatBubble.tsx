import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius } from '@theme/spacing';

interface ChatBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
  sources?: Array<{ filename?: string }>;
  timestamp?: number;
}

export function ChatBubble({ role, content, agent, sources, timestamp }: ChatBubbleProps) {
  const isUser = role === 'user';

  return (
    <View style={[styles.container, isUser ? styles.userContainer : styles.assistantContainer]}>
      <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        <Text style={[styles.content, isUser ? styles.userText : styles.assistantText]}>
          {content}
        </Text>
        {sources && sources.length > 0 && (
          <View style={styles.sourcesContainer}>
            <Text style={styles.sourcesLabel}>📖 المصادر:</Text>
            {sources.map((src, i) => (
              <Text key={i} style={styles.sourceItem}>
                [{i + 1}] {src.filename || 'وثيقة'}
              </Text>
            ))}
          </View>
        )}
        {agent && !isUser && (
          <Text style={styles.agentBadge}>🎯 {agent}</Text>
        )}
      </View>
      {timestamp && (
        <Text style={styles.timestamp}>
          {new Date(timestamp).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' })}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'column',
    marginVertical: spacing.xs,
    paddingHorizontal: spacing.md,
  },
  userContainer: {
    alignItems: 'flex-start',
  },
  assistantContainer: {
    alignItems: 'flex-end',
  },
  bubble: {
    maxWidth: '85%',
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
  },
  userBubble: {
    backgroundColor: colors.bubbleUser,
    borderBottomLeftRadius: radius.sm,
  },
  assistantBubble: {
    backgroundColor: colors.bubbleAssistant,
    borderBottomRightRadius: radius.sm,
    borderWidth: 1,
    borderColor: 'rgba(240,207,58,0.15)',
  },
  content: {
    ...typography.chatMessage,
  },
  userText: {
    color: colors.bubbleUserText,
  },
  assistantText: {
    color: colors.bubbleAssistantText,
  },
  sourcesContainer: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: 'rgba(240,207,58,0.2)',
  },
  sourcesLabel: {
    ...typography.caption,
    color: colors.hsaYellow,
    fontWeight: '700',
    marginBottom: 2,
  },
  sourceItem: {
    ...typography.caption,
    color: colors.textLight,
  },
  agentBadge: {
    ...typography.caption,
    color: colors.hsaYellow,
    fontWeight: '700',
    marginTop: spacing.xs,
  },
  timestamp: {
    ...typography.caption,
    color: colors.textMuted,
    fontSize: 9,
    marginTop: 2,
  },
});
