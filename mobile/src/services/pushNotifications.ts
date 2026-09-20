/**
 * HSAAI Mobile — Push Notification Service (Phase 11)
 * =====================================================
 * Enterprise push notifications via Expo Notifications + FCM/APNs.
 */
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
// FIX F-05: client is a default export — was using named import causing TS2305.
import client from '../api/client';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

class PushNotificationService {
  async register(): Promise<string | null> {
    // Check existing permissions
    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;

    if (existing !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') {
      console.warn('Push notification permission denied');
      return null;
    }

    // Get push token
    const token = (await Notifications.getExpoPushTokenAsync()).data;

    // Configure channel for Android
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'HSAAI Notifications',
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#2a6887',
      });

      // Create specialized channels
      await Notifications.setNotificationChannelAsync('tasks', {
        name: 'Task Assignments',
        importance: Notifications.AndroidImportance.HIGH,
      });
      await Notifications.setNotificationChannelAsync('approvals', {
        name: 'Approval Requests',
        importance: Notifications.AndroidImportance.MAX,
      });
      await Notifications.setNotificationChannelAsync('agents', {
        name: 'Agent Completions',
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    // Register token with backend
    try {
      await client.post('/v1/notifications/register', {
        token,
        platform: Platform.OS,
      });
    } catch (err) {
      console.warn('Failed to register push token:', err);
    }

    return token;
  }

  async unregister(): Promise<void> {
    try {
      await client.delete('/v1/notifications/register');
    } catch (err) {
      console.warn('Failed to unregister push token:', err);
    }
  }

  // Local notification (for foreground)
  async showLocal(title: string, body: string, data?: any) {
    await Notifications.scheduleNotificationAsync({
      content: { title, body, data, sound: true },
      trigger: null, // immediately
    });
  }

  // Badge count
  async setBadgeCount(count: number) {
    await Notifications.setBadgeCountAsync(count);
  }

  async clearBadge() {
    await Notifications.setBadgeCountAsync(0);
  }
}

export const pushNotifications = new PushNotificationService();
