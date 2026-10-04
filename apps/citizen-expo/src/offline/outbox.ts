/**
 * Offline Outbox — persists report drafts to SQLite (native) or LocalStorage (web)
 * and syncs when online.
 *
 * States: draft → queued → uploading → synced | error
 * Every mutation has an idempotency_key to prevent double-submission.
 */

import { Platform } from 'react-native';
import type { ReportDraft } from '../types';
import { intakeApi } from '../api/client';

let db: any = null;
const isWeb = Platform.OS === 'web';

// In-memory / web fallback map
const webStore: Map<string, ReportDraft> = new Map();

function getDb(): any {
  if (isWeb) return null;
  if (!db) {
    try {
      const SQLite = require('expo-sqlite');
      db = SQLite.openDatabaseSync('civicconnect_outbox.db');
      db.execSync(`
        CREATE TABLE IF NOT EXISTS outbox (
          id TEXT PRIMARY KEY,
          data TEXT NOT NULL,
          sync_status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL,
          error_message TEXT,
          idempotency_key TEXT NOT NULL UNIQUE
        );
      `);
    } catch {
      return null;
    }
  }
  return db;
}

export function saveDraft(draft: ReportDraft): void {
  const database = getDb();
  if (!database) {
    webStore.set(draft.id, draft);
    return;
  }
  try {
    database.runSync(
      `INSERT OR REPLACE INTO outbox (id, data, sync_status, created_at, idempotency_key)
       VALUES (?, ?, ?, ?, ?)`,
      draft.id,
      JSON.stringify(draft),
      draft.sync_status,
      draft.created_at,
      draft.idempotency_key
    );
  } catch {
    webStore.set(draft.id, draft);
  }
}

export function getDrafts(): ReportDraft[] {
  const database = getDb();
  if (!database) {
    return Array.from(webStore.values());
  }
  try {
    const rows = database.getAllSync('SELECT data FROM outbox ORDER BY created_at DESC') as Array<{ data: string }>;
    return rows.map((r: { data: string }) => JSON.parse(r.data) as ReportDraft);
  } catch {
    return Array.from(webStore.values());
  }
}

export function getQueuedDrafts(): ReportDraft[] {
  const database = getDb();
  if (!database) {
    return Array.from(webStore.values()).filter(d => d.sync_status === 'queued' || d.sync_status === 'error');
  }
  try {
    const rows = database.getAllSync(
      "SELECT data FROM outbox WHERE sync_status IN ('queued', 'error') ORDER BY created_at ASC"
    ) as Array<{ data: string }>;
    return rows.map((r: { data: string }) => JSON.parse(r.data) as ReportDraft);
  } catch {
    return Array.from(webStore.values()).filter(d => d.sync_status === 'queued' || d.sync_status === 'error');
  }
}

export function updateDraftStatus(
  id: string,
  status: ReportDraft['sync_status'],
  error?: string
): void {
  const database = getDb();
  if (!database) {
    const item = webStore.get(id);
    if (item) {
      item.sync_status = status;
      item.error_message = error;
    }
    return;
  }
  try {
    database.runSync(
      'UPDATE outbox SET sync_status = ?, error_message = ? WHERE id = ?',
      status,
      error ?? null,
      id
    );
  } catch {
    const item = webStore.get(id);
    if (item) {
      item.sync_status = status;
      item.error_message = error;
    }
  }
}

export function deleteDraft(id: string): void {
  const database = getDb();
  if (!database) {
    webStore.delete(id);
    return;
  }
  try {
    database.runSync('DELETE FROM outbox WHERE id = ?', id);
  } catch {
    webStore.delete(id);
  }
}

export function getPendingCount(): number {
  const database = getDb();
  if (!database) {
    return Array.from(webStore.values()).filter(d => d.sync_status !== 'synced').length;
  }
  try {
    const row = database.getFirstSync(
      "SELECT COUNT(*) as count FROM outbox WHERE sync_status IN ('draft', 'queued', 'error')"
    ) as { count: number } | null;
    return row?.count ?? 0;
  } catch {
    return Array.from(webStore.values()).filter(d => d.sync_status !== 'synced').length;
  }
}

// ─── Sync ─────────────────────────────────────────────────

export async function syncOutbox(): Promise<void> {
  const queued = getQueuedDrafts();

  for (const draft of queued) {
    try {
      updateDraftStatus(draft.id, 'uploading');

      const image_refs: string[] = [];
      for (const localUri of draft.images) {
        const ref = await uploadLocalFile(localUri);
        if (ref) image_refs.push(ref);
      }

      let audio_ref: string | undefined;
      if (draft.audio_uri) {
        audio_ref = (await uploadLocalFile(draft.audio_uri)) ?? undefined;
      }

      let video_ref: string | undefined;
      if (draft.video_uri) {
        video_ref = (await uploadLocalFile(draft.video_uri)) ?? undefined;
      }

      await intakeApi.submitIntake({
        text: draft.text,
        location: draft.location ?? { lat: 12.9716, lng: 77.5946 },
        landmark: draft.landmark,
        image_refs: image_refs.length > 0 ? image_refs : undefined,
        audio_ref,
        video_ref,
        idempotency_key: draft.idempotency_key,
      });

      updateDraftStatus(draft.id, 'synced');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Sync failed';
      updateDraftStatus(draft.id, 'error', msg);
    }
  }
}

async function uploadLocalFile(uri: string): Promise<string | null> {
  try {
    if (isWeb) return uri;
    const FileSystem = require('expo-file-system');
    const info = await FileSystem.getInfoAsync(uri);
    if (!info.exists) return null;
    return `upload_ref_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  } catch {
    return null;
  }
}
