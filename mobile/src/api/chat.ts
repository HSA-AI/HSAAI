import client from './client';

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
  sources?: Array<{ filename?: string; score?: number }>;
  createdAt?: number;
}

export interface ChatResponse {
  response: string;
  agent?: string;
  sources?: Array<{ filename?: string; score?: number }>;
  latency_ms?: number;
}

export async function sendChatMessage(
  message: string,
  workspaceId: string = 'hsa-main-workspace',
  user: string = 'employee',
): Promise<ChatResponse> {
  const { data } = await client.post('/v1/chat', {
    user,
    message,
    workspace_id: workspaceId,
  });
  return data;
}

export async function getChatHistory(conversationId: string): Promise<ChatMessage[]> {
  const { data } = await client.get(`/v1/chat/history/${conversationId}`);
  return data.messages || [];
}

export async function getConversations() {
  const { data } = await client.get('/v1/chat/conversations');
  return data.conversations || [];
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await client.delete(`/v1/chat/conversations/${conversationId}`);
}

export async function startNewConversation(): Promise<string> {
  const { data } = await client.post('/v1/chat/conversations');
  return data.conversation_id;
}
