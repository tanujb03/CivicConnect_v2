// Unit tests for outbox/core.ts
// Run with: node --test src/outbox/__tests__/core.test.js
// (no expo or react-native needed)
//
// The file is plain JS so Node's built-in test runner can execute it
// without a TypeScript compile step.

const { createOutboxCore, nextRetryAt, MAX_ATTEMPTS } = require('../core.js');
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeStorage(initial = []) {
  let items = [...initial];
  let counter = 0;
  return {
    async enqueue(input) {
      const id = `item-${++counter}`;
      items.push({
        ...input,
        id,
        status: 'PENDING',
        createdAt: new Date().toISOString(),
        attempts: 0,
      });
      return id;
    },
    async loadPending() {
      return items.filter(i => i.status === 'PENDING');
    },
    async markSent(id) {
      items = items.filter(i => i.id !== id);
    },
    async markFailed(id, reason, nextRetryAt) {
      const item = items.find(i => i.id === id);
      if (item) {
        item.status = 'FAILED';
        item.lastError = reason;
        item.nextRetryAt = nextRetryAt;
        item.attempts = (item.attempts || 0) + 1;
        // Keep as PENDING so it can be retried
        item.status = 'PENDING';
      }
    },
    async remove(id) {
      items = items.filter(i => i.id !== id);
    },
    _items: () => items,
  };
}

const alwaysOnline = { isOnline: async () => true };
const alwaysOffline = { isOnline: async () => false };
const successSender = { send: async () => {} };
const failSender = { send: async () => { throw new Error('network error'); } };

// ── Tests ────────────────────────────────────────────────────────────────────

describe('outbox core', () => {

  test('enqueue stores an item and returns an id', async () => {
    const storage = makeStorage();
    const core = createOutboxCore(storage, alwaysOnline, successSender);
    const id = await core.enqueue({ type: 'WORK_ORDER_UPDATE', workOrderId: 'wo-1', payload: {} });
    assert.ok(id, 'id should be truthy');
    const pending = await core.getPending();
    assert.equal(pending.length, 1);
    assert.equal(pending[0].id, id);
  });

  test('flush returns 0 when offline', async () => {
    const storage = makeStorage();
    const core = createOutboxCore(storage, alwaysOffline, successSender);
    await core.enqueue({ type: 'WORK_ORDER_UPDATE', workOrderId: 'wo-1', payload: {} });
    const flushed = await core.flush();
    assert.equal(flushed, 0);
    const pending = await core.getPending();
    assert.equal(pending.length, 1, 'item should still be pending when offline');
  });

  test('flush removes item after successful send', async () => {
    const storage = makeStorage();
    const core = createOutboxCore(storage, alwaysOnline, successSender);
    await core.enqueue({ type: 'WORK_ORDER_UPDATE', workOrderId: 'wo-1', payload: {} });
    const flushed = await core.flush();
    assert.equal(flushed, 1);
    const pending = await core.getPending();
    assert.equal(pending.length, 0);
  });

  test('flush keeps item on failure and increments attempts', async () => {
    const storage = makeStorage();
    const core = createOutboxCore(storage, alwaysOnline, failSender);
    await core.enqueue({ type: 'WORK_ORDER_UPDATE', workOrderId: 'wo-1', payload: {} });
    const flushed = await core.flush();
    assert.equal(flushed, 0);
    const pending = await core.getPending();
    assert.equal(pending.length, 1);
    assert.equal(pending[0].attempts, 1);
    assert.ok(pending[0].lastError, 'lastError should be set');
  });

  test('flush removes item after MAX_ATTEMPTS failures', async () => {
    const preLoaded = [{
      id: 'item-99',
      type: 'WORK_ORDER_UPDATE',
      workOrderId: 'wo-1',
      payload: {},
      status: 'PENDING',
      createdAt: new Date().toISOString(),
      attempts: MAX_ATTEMPTS - 1,
    }];
    const storage = makeStorage(preLoaded);
    const core = createOutboxCore(storage, alwaysOnline, failSender);
    await core.flush();
    const pending = await core.getPending();
    assert.equal(pending.length, 0, 'item should be removed after max attempts');
  });

  test('flush skips items whose nextRetryAt is in the future', async () => {
    const future = new Date(Date.now() + 3_600_000).toISOString();
    const preLoaded = [{
      id: 'item-future',
      type: 'WORK_ORDER_UPDATE',
      workOrderId: 'wo-1',
      payload: {},
      status: 'PENDING',
      createdAt: new Date().toISOString(),
      attempts: 1,
      nextRetryAt: future,
    }];
    const storage = makeStorage(preLoaded);
    const core = createOutboxCore(storage, alwaysOnline, successSender);
    const flushed = await core.flush();
    assert.equal(flushed, 0, 'should not flush items with future retry time');
    const pending = await core.getPending();
    assert.equal(pending.length, 1);
  });

  test('nextRetryAt increases with attempt count', () => {
    const t0 = Date.now();
    const r0 = new Date(nextRetryAt(0)).getTime();
    const r1 = new Date(nextRetryAt(1)).getTime();
    const r2 = new Date(nextRetryAt(2)).getTime();
    assert.ok(r1 > r0, 'attempt 1 retry should be later than attempt 0');
    assert.ok(r2 > r1, 'attempt 2 retry should be later than attempt 1');
    assert.ok(r0 > t0, 'retry should be in the future');
  });

});
