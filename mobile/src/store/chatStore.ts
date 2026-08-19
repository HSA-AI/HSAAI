import { create } from 'zustand';
import type { ChatMessage } from '@api/chat';
import { sendChatMessage } from '@api/chat';
import {
  createConversation as dbCreateConversation,
  getConversations as dbGetConversations,
  getMessages as dbGetMessages,
  saveMessage as dbSaveMessage,
  deleteConversation as dbDeleteConversation,
  type Conversation,
} from '@db/chatRepository';
import NetInfo from '@react-native-community/netinfo';

interface ChatState {
  conversations: Conversation[];
  currentMessages: ChatMessage[];
  currentConversationId: string | null;
  isLoading: boolean;
  isSending: boolean;
  isOffline: boolean;
  error: string | null;

  loadConversations: () => Promise<void>;
  loadMessages: (conversationId: string) => Promise<void>;
  startNewConversation: () => Promise<string>;
  sendMessage: (text: string, workspaceId?: string) => Promise<void>;
  removeConversation: (id: string) => Promise<void>;
  setOffline: (offline: boolean) => void;
  clearError: () => void;
}

const WELCOME_MESSAGE: Omit<ChatMessage, 'id'> = {
  role: 'assistant',
  content:
    'مرحباً، أنا مساعد HSAAI الداخلي. اسألني عن السياسات، المستندات، الأنظمة، أو أي خدمة مؤسسية مصرح لك بها.',
};

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentMessages: [],
  currentConversationId: null,
  isLoading: false,
  isSending: false,
  isOffline: false,
  error: null,

  loadConversations: async () => {
    set({ isLoading: true });
    try {
      const convs = await dbGetConversations();
      set({ conversations: convs, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: 'فشل تحميل المحادثات' });
    }
  },

  loadMessages: async (conversationId: string) => {
    set({ isLoading: true, currentConversationId: conversationId });
    try {
      const messages = await dbGetMessages(conversationId);
      set({ currentMessages: messages, isLoading: false });
    } catch {
      set({ isLoading: false, error: 'فشل تحميل الرسائل' });
    }
  },

  startNewConversation: async () => {
    const conversationId = `conv-${Date.now()}`;
    const title = `محادثة ${new Date().toLocaleString('ar')}`;
    await dbCreateConversation(conversationId, title);

    // Save welcome message
    const welcomeId = await dbSaveMessage(conversationId, WELCOME_MESSAGE);

    set({
      currentConversationId: conversationId,
      currentMessages: [{ ...WELCOME_MESSAGE, id: welcomeId }],
    });

    // Reload conversation list
    await get().loadConversations();

    return conversationId;
  },

  sendMessage: async (text: string, workspaceId: string = 'hsa-main-workspace') => {
    const { currentConversationId, isOffline } = get();
    if (!currentConversationId || !text.trim()) return;

    // Save user message locally
    const userMsg: Omit<ChatMessage, 'id'> = {
      role: 'user',
      content: text,
      createdAt: Date.now(),
    };
    const userMsgId = await dbSaveMessage(currentConversationId, userMsg);
    set((state) => ({
      currentMessages: [...state.currentMessages, { ...userMsg, id: userMsgId }],
      isSending: true,
      error: null,
    }));

    // If offline, queue for later
    if (isOffline) {
      const offlineMsg: Omit<ChatMessage, 'id'> = {
        role: 'assistant',
        content: '⚠️ أنت غير متصل بالإنترنت. سيتم الرد عند عودة الاتصال.',
        createdAt: Date.now(),
      };
      const offlineId = await dbSaveMessage(currentConversationId, offlineMsg);
      set((state) => ({
        currentMessages: [...state.currentMessages, { ...offlineMsg, id: offlineId }],
        isSending: false,
      }));
      return;
    }

    // Send to API
    try {
      const response = await sendChatMessage(text, workspaceId);
      const assistantMsg: Omit<ChatMessage, 'id'> = {
        role: 'assistant',
        content: response.response,
        agent: response.agent,
        sources: response.sources,
        createdAt: Date.now(),
      };
      const assistantId = await dbSaveMessage(currentConversationId, assistantMsg);
      set((state) => ({
        currentMessages: [...state.currentMessages, { ...assistantMsg, id: assistantId }],
        isSending: false,
      }));
    } catch (err) {
      const errorMsg: Omit<ChatMessage, 'id'> = {
        role: 'assistant',
        content: 'تعذر الاتصال بخدمة HSAAI حالياً. تأكد من اتصالك بالشبكة الداخلية أو جرّب لاحقاً.',
        createdAt: Date.now(),
      };
      const errorId = await dbSaveMessage(currentConversationId, errorMsg);
      set((state) => ({
        currentMessages: [...state.currentMessages, { ...errorMsg, id: errorId }],
        isSending: false,
        error: 'فشل إرسال الرسالة',
      }));
    }
  },

  removeConversation: async (id: string) => {
    await dbDeleteConversation(id);
    await get().loadConversations();
    if (get().currentConversationId === id) {
      set({ currentConversationId: null, currentMessages: [] });
    }
  },

  setOffline: (offline: boolean) => set({ isOffline: offline }),
  clearError: () => set({ error: null }),
}));

// Subscribe to network state changes
NetInfo.addEventListener((state) => {
  useChatStore.getState().setOffline(!state.isConnected);
});
