import { useEffect, useState } from 'react';
import * as Network from 'expo-network';

export function useNetwork() {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function check() {
      try {
        const state = await Network.getNetworkStateAsync();
        if (mounted) {
          // If internet reachability is known to be false, mark offline
          const online = state.isConnected !== false && state.isInternetReachable !== false;
          setIsOnline(online);
        }
      } catch {
        // Fallback to online if permission/check fails
        if (mounted) setIsOnline(true);
      }
    }

    check();
    const interval = setInterval(check, 10000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { isOnline };
}
