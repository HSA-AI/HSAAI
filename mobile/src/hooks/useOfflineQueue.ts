/**
 * HSAAI Mobile — useOfflineQueue Hook (Phase 11)
 * ================================================
 * React hook for managing offline operation queue.
 */
import { useState, useEffect, useCallback } from 'react';
import { offlineSync } from '../services/offlineSync';

export function useOfflineQueue() {
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    const unsubscribe = offlineSync.onStatusChange((status) => {
      setPendingCount(status.pending);
      setIsSyncing(status.syncing);
    });
    offlineSync.getPendingCount().then(setPendingCount);
    return unsubscribe;
  }, []);

  const queueOperation = useCallback(async (op: any) => {
    await offlineSync.queueOperation(op);
    const count = await offlineSync.getPendingCount();
    setPendingCount(count);
  }, []);

  const syncNow = useCallback(async () => {
    await offlineSync.sync();
  }, []);

  return { pendingCount, isSyncing, queueOperation, syncNow };
}
