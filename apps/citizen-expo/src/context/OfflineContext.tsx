import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import NetInfo from '@react-native-community/netinfo';
import { getPendingCount, syncOutbox } from '../offline/outbox';

interface OfflineContextValue {
  isOnline: boolean;
  isLowBandwidth: boolean;
  pendingCount: number;
  triggerSync: () => Promise<void>;
  isSyncing: boolean;
}

const OfflineContext = createContext<OfflineContextValue>({
  isOnline: true,
  isLowBandwidth: false,
  pendingCount: 0,
  triggerSync: async () => {},
  isSyncing: false,
});

export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const [isOnline, setIsOnline] = useState(true);
  const [isLowBandwidth, setIsLowBandwidth] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    setPendingCount(getPendingCount());
  }, []);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener(state => {
      const connected = state.isConnected ?? false;
      setIsOnline(connected);
      setIsLowBandwidth(
        (state.type as string) === '2g' ||
        (state.type === 'cellular' && (state.details as any)?.cellularGeneration === '2g')
      );

      if (connected) {
        // Auto-sync when connectivity is restored
        triggerSync();
      }
    });
    return () => unsubscribe();
  }, []);

  const triggerSync = useCallback(async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    try {
      await syncOutbox();
      setPendingCount(getPendingCount());
    } finally {
      setIsSyncing(false);
    }
  }, [isSyncing]);

  return (
    <OfflineContext.Provider value={{ isOnline, isLowBandwidth, pendingCount, triggerSync, isSyncing }}>
      {children}
    </OfflineContext.Provider>
  );
}

export function useOffline() {
  return useContext(OfflineContext);
}
