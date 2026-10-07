// Plain CommonJS version of outbox core for Node.js unit testing
// This is a copy of core.ts compiled to JS so tests can run without tsc

'use strict';

const MAX_ATTEMPTS = 5;

const RETRY_DELAYS_MS = [30_000, 120_000, 600_000, 1_800_000, 3_600_000];

function nextRetryAt(attempts) {
  const ms = RETRY_DELAYS_MS[Math.min(attempts, RETRY_DELAYS_MS.length - 1)];
  return new Date(Date.now() + ms).toISOString();
}

function createOutboxCore(storage, network, sender) {
  return {
    async enqueue(input) {
      return storage.enqueue(input);
    },

    async flush() {
      const online = await network.isOnline();
      if (!online) return 0;

      const pending = await storage.loadPending();
      const now = Date.now();

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
            await storage.remove(item.id);
          } else {
            const reason = err instanceof Error ? err.message : String(err);
            await storage.markFailed(item.id, reason, nextRetryAt(newAttempts));
          }
        }
      }
      return flushed;
    },

    async getPending() {
      return storage.loadPending();
    },
  };
}

module.exports = { createOutboxCore, nextRetryAt, MAX_ATTEMPTS };
