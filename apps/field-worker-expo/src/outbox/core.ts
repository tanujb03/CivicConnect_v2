// Outbox core engine — pure business logic, NO native imports
// All I/O is injected via StoragePort, NetworkPort and SenderPort

import type { StoragePort, NetworkPort, SenderPort, OutboxItem, OutboxItemInput } from './ports';

const MAX_ATTEMPTS = 5;

// Exponential back-off: 30s, 2m, 10m, 30m, 1h
const RETRY_DELAYS_MS = [30_000, 120_000, 600_000, 1_800_000, 3_600_000];

function nextRetryAt(attempts: number): string {
  const ms = RETRY_DELAYS_MS[Math.min(attempts, RETRY_DELAYS_MS.length - 1)];
  return new Date(Date.now() + ms).toISOString();
}

export interface OutboxCore {
  /** Add an item to the outbox. Returns the generated id. */
  enqueue(input: OutboxItemInput): Promise<string>;
  /** Attempt to flush all eligible pending items. Returns flushed count. */
  flush(): Promise<number>;
  /** Load all items currently in the outbox. */
  getPending(): Promise<OutboxItem[]>;
}

export function createOutboxCore(
  storage: StoragePort,
  network: NetworkPort,
  sender: SenderPort,
): OutboxCore {
  return {
    async enqueue(input: OutboxItemInput): Promise<string> {
      return storage.enqueue(input);
    },

    async flush(): Promise<number> {
      const online = await network.isOnline();
      if (!online) return 0;

      const pending = await storage.loadPending();
      const now = Date.now();

      // Filter out items that are not yet due for retry
      const eligible = pending.filter(item => {
        if (item.nextRetryAt) {
          return new Date(item.nextRetryAt).getTime() <= now;
        }
        return true;
      });

      let flushed = 0;
      for (const item of eligible) {
        try {
          await sender.send(item);
          await storage.markSent(item.id);
          flushed++;
        } catch (err) {
          const newAttempts = item.attempts + 1;
          if (newAttempts >= MAX_ATTEMPTS) {
            // Give up — move to dead letter by removing
            await storage.remove(item.id);
          } else {
            const reason = err instanceof Error ? err.message : String(err);
            await storage.markFailed(item.id, reason, nextRetryAt(newAttempts));
          }
        }
      }
      return flushed;
    },

    async getPending(): Promise<OutboxItem[]> {
      return storage.loadPending();
    },
  };
}

// ── Pure helpers exported for unit testing ────────────────────────────────

export { nextRetryAt };
export { MAX_ATTEMPTS };
