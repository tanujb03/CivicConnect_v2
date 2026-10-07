// Outbox port interfaces — injected so core.ts has zero native imports
// These are the only abstractions core.ts depends on

export interface StoragePort {
  /** Persist an item to durable storage. Returns the persisted id. */
  enqueue(item: OutboxItemInput): Promise<string>;
  /** Load all pending items sorted by createdAt asc. */
  loadPending(): Promise<OutboxItem[]>;
  /** Mark an item as successfully sent. */
  markSent(id: string): Promise<void>;
  /** Mark an item as failed with a reason. */
  markFailed(id: string, reason: string, nextRetryAt: string): Promise<void>;
  /** Permanently delete an item (after max retries). */
  remove(id: string): Promise<void>;
}

export interface NetworkPort {
  /** Returns true if the device has a network connection. */
  isOnline(): Promise<boolean>;
}

export interface SenderPort {
  /** Send a single outbox item to the backend. Throws on failure. */
  send(item: OutboxItem): Promise<void>;
}

// ── Data shapes ─────────────────────────────────────────────────────────────

export type OutboxItemType = 'WORK_ORDER_UPDATE' | 'PHOTO_UPLOAD';

export interface OutboxItemInput {
  type: OutboxItemType;
  workOrderId: string;
  payload: Record<string, unknown>;
}

export interface OutboxItem extends OutboxItemInput {
  id: string;
  status: 'PENDING' | 'FAILED';
  createdAt: string;
  attempts: number;
  lastError?: string;
  nextRetryAt?: string;
}
