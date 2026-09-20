import client from './client';

export interface AppNotification {
  id: string;
  type: 'approval' | 'alert' | 'info' | 'security' | 'system';
  title: string;
  body: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  read: boolean;
  createdAt: string;
  actionUrl?: string;
  actionLabel?: string;
}

export async function getNotifications(unreadOnly: boolean = false): Promise<AppNotification[]> {
  const params = unreadOnly ? { unread: true } : {};
  const { data } = await client.get('/v1/notifications', { params });
  return data.notifications || [];
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/v1/notifications/${notificationId}/read`);
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/v1/notifications/read-all');
}

export async function registerPushToken(token: string, platform: 'android' | 'ios'): Promise<void> {
  await client.post('/v1/notifications/register', { token, platform });
}

export async function getUnreadCount(): Promise<number> {
  const { data } = await client.get('/v1/notifications/unread-count');
  return data.count || 0;
}
