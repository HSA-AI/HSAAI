import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { HSAHeader, ChatBubble } from '@components/index';
import { useChatStore } from '@store/chatStore';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';

const QUICK_PROMPTS = [
  'ما سياسة الإجازات؟',
  'ابحث في مستندات المؤسسة',
  'من هو هيثم؟',
  'لخص آخر تقرير متاح',
];

export function ChatScreen() {
  const {
    currentMessages,
    currentConversationId,
    isSending,
    isOffline,
    startNewConversation,
    sendMessage,
    loadConversations,
  } = useChatStore();

  const [input, setInput] = useState('');
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    loadConversations();
    if (!currentConversationId) {
      startNewConversation();
    }
  }, []);

  useEffect(() => {
    if (currentMessages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [currentMessages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput('');
    await sendMessage(text);
  };

  const handleQuickPrompt = async (prompt: string) => {
    if (isSending) return;
    setInput('');
    await sendMessage(prompt);
  };

  const renderMessage = ({ item }) => (
    <ChatBubble
      role={item.role}
      content={item.content}
      agent={item.agent}
      sources={item.sources}
      timestamp={item.createdAt}
    />
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <HSAHeader
        title="المساعد الذكي"
        subtitle={isOffline ? '⚠️ غير متصل' : 'HSAAI Assistant'}
        rightAction={
          <TouchableOpacity onPress={() => startNewConversation()} style={styles.newChatButton}>
            <Icon name="plus-circle-outline" size={24} color={colors.hsaYellow} />
          </TouchableOpacity>
        }
      />

      {isOffline && (
        <View style={styles.offlineBanner}>
          <Icon name="wifi-off" size={16} color={colors.warning} />
          <Text style={styles.offlineText}>غير متصل — الرسائل ستُحفظ محلياً</Text>
        </View>
      )}

      <FlatList
        ref={flatListRef}
        data={currentMessages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id || `${item.createdAt}`}
        contentContainerStyle={styles.messagesList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
      />

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {/* Quick prompts */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.quickPromptsContainer}
        >
          {QUICK_PROMPTS.map((prompt, i) => (
            <TouchableOpacity
              key={i}
              style={styles.quickPrompt}
              onPress={() => handleQuickPrompt(prompt)}
              disabled={isSending}
            >
              <Text style={styles.quickPromptText}>{prompt}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Input */}
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="اكتب استفسارك هنا..."
            placeholderTextColor={colors.textLight}
            multiline
            maxLength={2000}
            textAlign="right"
            editable={!isSending}
          />
          <TouchableOpacity
            style={[styles.sendButton, (!input.trim() || isSending) && styles.sendButtonDisabled]}
            onPress={handleSend}
            disabled={!input.trim() || isSending}
          >
            {isSending ? (
              <ActivityIndicator size="small" color={colors.hsaBlack} />
            ) : (
              <Icon name="send" size={20} color={colors.hsaBlack} />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// Need to import ScrollView
import { ScrollView } from 'react-native';

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  newChatButton: { padding: spacing.xs },
  offlineBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.warningBg,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.lg,
  },
  offlineText: { ...typography.caption, color: colors.warning, fontWeight: '600' },
  messagesList: {
    paddingVertical: spacing.md,
    paddingBottom: spacing.sm,
  },
  quickPromptsContainer: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  quickPrompt: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: 'rgba(240,207,58,0.3)',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    marginLeft: spacing.xs,
  },
  quickPromptText: {
    ...typography.caption,
    color: colors.hsaYellow,
    fontWeight: '600',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderDark,
  },
  input: {
    ...typography.chatInput,
    color: colors.textWhite,
    flex: 1,
    maxHeight: 100,
    minHeight: 40,
    paddingHorizontal: spacing.sm,
    textAlign: 'right',
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.hsaYellow,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: spacing.sm,
  },
  sendButtonDisabled: {
    backgroundColor: colors.textLight,
  },
});
