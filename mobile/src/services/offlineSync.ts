/**
 * HSAAI Mobile — Offline Sync Service (Phase 11)
 * =================================================
 * Background sync with conflict resolution.
 * Uses SQLite for local cache + queue of pending operations.
 */
import NetInfo from '@react-native-community/netinfo';
import AsyncStorage from '@react-native-async-storage/async-storage';
// FIX F-05: client is a default export — was using named import causing TS2305.
import client from '../api/client';

const PENDING_OPS_KEY = '@hsaai/pending_ops';
const LAST_SYNC_KEY = '@hsaai/last_sync';

type PendingOp = {
  id: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  data?: any;
  timestamp: number;
  retries: number;
};

class OfflineSyncService {
  private isSyncing = false;
  private listeners: Set<(status: SyncStatus) => void> = new Set();
  private unsubscribe: (() => void) | null = null;

  start() {
    // Subscribe to network state changes
    this.unsubscribe = NetInfo.addEventListener(state => {
      if (state.isConnected && state.isInternetReachable) {
        this.sync();
      }
    });
    // Initial sync attempt
    setTimeout(() => this.sync(), 2000);
  }

  stop() {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
  }

  onStatusChange(cb: (status: SyncStatus) => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  private notify(status: SyncStatus) {
    this.listeners.forEach(cb => cb(status));
  }

  async queueOperation(op: Omit<PendingOp, 'id' | 'timestamp' | 'retries'>) {
    const pending: PendingOp[] = JSON.parse(
      (await AsyncStorage.getItem(PENDING_OPS_KEY)) || '[]'
    );
    const newOp: PendingOp = {
      ...op,
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: Date.now(),
      retries: 0,
    };
    pending.push(newOp);
    await AsyncStorage.setItem(PENDING_OPS_KEY, JSON.stringify(pending));
    this.notify({ pending: pending.length, syncing: false });
  }

  async getPendingCount(): Promise<number> {
    const pending: PendingOp[] = JSON.parse(
      (await AsyncStorage.getItem(PENDING_OPS_KEY)) || '[]'
    );
    return pending.length;
  }

  async sync() {
    if (this.isSyncing) return;
    const netState = await NetInfo.fetch();
    if (!netState.isConnected) return;

    this.isSyncing = true;
    this.notify({ pending: await this.getPendingCount(), syncing: true });

    try {
      const pending: PendingOp[] = JSON.parse(
        (await AsyncStorage.getItem(PENDING_OPS_KEY)) || '[]'
      );

      if (pending.length === 0) {
        this.notify({ pending: 0, syncing: false, lastSync: new Date().toISOString() });
        return;
      }

      // Sort by timestamp (FIFO)
      pending.sort((a, b) => a.timestamp - b.timestamp);

      const failed: PendingOp[] = [];
      for (const op of pending) {
        try {
          await client.request({
            method: op.method,
            url: op.url,
            data: op.data,
          });
        } catch (err) {
          op.retries += 1;
          if (op.retries < 5) {
            failed.push(op);
          }
        }
      }

      await AsyncStorage.setItem(PENDING_OPS_KEY, JSON.stringify(failed));
      await AsyncStorage.setItem(LAST_SYNC_KEY, new Date().toISOString());

      this.notify({
        pending: failed.length,
        syncing: false,
        lastSync: new Date().toISOString(),
        failed: pending.length - failed.length,
      });
    } catch (err) {
      this.notify({ pending: 0, syncing: false, error: String(err) });
    } finally {
      this.isSyncing = false;
    }
  }

  async getLastSync(): Promise<string | null> {
    return AsyncStorage.getItem(LAST_SYNC_KEY);
  }
}

interface SyncStatus {
  pending: number;
  syncing: boolean;
  lastSync?: string;
  failed?: number;
  error?: string;
}

export const offlineSync = new OfflineSyncService();
