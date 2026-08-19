import { getDatabase } from './database';
import type { ChatMessage } from '@api/chat';

// ── Conversations ──
export interface Conversation {
  id: string;
  title: string;
  workspaceId: string;
  createdAt: number;
  updatedAt: number;
  synced: boolean;
}

export async function createConversation(
  id: string,
  title: string,
  workspaceId: string = 'hsa-main-workspace',
): Promise<void> {
  const db = await getDatabase();
  const now = Date.now();
  await db.executeSql(
    `INSERT OR REPLACE INTO conversations (id, title, workspace_id, created_at, updated_at, synced) VALUES (?, ?, ?, ?, ?, 0)`,
    [id, title, workspaceId, now, now],
  );
}

export async function getConversations(): Promise<Conversation[]> {
  const db = await getDatabase();
  const [results] = await db.executeSql(
    `SELECT * FROM conversations ORDER BY updated_at DESC`,
  );

  const conversations: Conversation[] = [];
  for (let i = 0; i < results.rows.length; i++) {
    const row = results.rows.item(i);
    conversations.push({
      id: row.id,
      title: row.title,
      workspaceId: row.workspace_id,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      synced: row.synced === 1,
    });
  }
  return conversations;
}

export async function deleteConversation(id: string): Promise<void> {
  const db = await getDatabase();
  await db.executeSql(`DELETE FROM messages WHERE conversation_id = ?`, [id]);
  await db.executeSql(`DELETE FROM conversations WHERE id = ?`, [id]);
}

// ── Messages ──
export async function saveMessage(
  conversationId: string,
  message: Omit<ChatMessage, 'id'> & { id?: string },
): Promise<string> {
  const db = await getDatabase();
  const msgId = message.id || `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const sources = message.sources ? JSON.stringify(message.sources) : null;
  const now = message.createdAt || Date.now();

  await db.executeSql(
    `INSERT OR REPLACE INTO messages (id, conversation_id, role, content, agent, sources, created_at, synced) VALUES (?, ?, ?, ?, ?, ?, ?, 0)`,
    [msgId, conversationId, message.role, message.content, message.agent || null, sources, now],
  );

  // Update conversation timestamp
  await db.executeSql(
    `UPDATE conversations SET updated_at = ? WHERE id = ?`,
    [now, conversationId],
  );

  return msgId;
}

export async function getMessages(conversationId: string): Promise<ChatMessage[]> {
  const db = await getDatabase();
  const [results] = await db.executeSql(
    `SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC`,
    [conversationId],
  );

  const messages: ChatMessage[] = [];
  for (let i = 0; i < results.rows.length; i++) {
    const row = results.rows.item(i);
    messages.push({
      id: row.id,
      role: row.role,
      content: row.content,
      agent: row.agent || undefined,
      sources: row.sources ? JSON.parse(row.sources) : undefined,
      createdAt: row.created_at,
    });
  }
  return messages;
}

export async function getUnsyncedMessages(): Promise<ChatMessage[]> {
  const db = await getDatabase();
  const [results] = await db.executeSql(
    `SELECT * FROM messages WHERE synced = 0 ORDER BY created_at ASC`,
  );

  const messages: ChatMessage[] = [];
  for (let i = 0; i < results.rows.length; i++) {
    const row = results.rows.item(i);
    messages.push({
      id: row.id,
      role: row.role,
      content: row.content,
      agent: row.agent || undefined,
      createdAt: row.created_at,
    });
  }
  return messages;
}

export async function markMessageSynced(messageId: string): Promise<void> {
  const db = await getDatabase();
  await db.executeSql(`UPDATE messages SET synced = 1 WHERE id = ?`, [messageId]);
}
