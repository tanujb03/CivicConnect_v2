/**
 * useNetworkStatus — monitors connectivity for offline UI
 */

import { useState, useEffect } from 'react';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';

export interface NetworkStatus {
  isConnected: boolean;
  isInternetReachable: boolean;
  type: string;
  isLowBandwidth: boolean;
}

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({
    isConnected: true,
    isInternetReachable: true,
    type: 'unknown',
    isLowBandwidth: false,
  });

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state: NetInfoState) => {
      const isLowBandwidth =
        (state.type as string) === '2g' ||
        (state.type === 'cellular' && (state.details as any)?.cellularGeneration === '2g');

      setStatus({
        isConnected: state.isConnected ?? false,
        isInternetReachable: state.isInternetReachable ?? false,
        type: state.type,
        isLowBandwidth,
      });
    });

    return () => unsubscribe();
  }, []);

  return status;
}
