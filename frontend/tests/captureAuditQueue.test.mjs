import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createCaptureAuditQueue, newAuditId } from '../src/lib/captureAuditQueue.js';

test('starts once and sends selections in order before flush completes', async () => {
    const calls = [];
    const queue = createCaptureAuditQueue({
        start: async () => calls.push('start'),
        send: async (event) => calls.push(event),
    });
    const first = queue.record('field_changed', { field: 'category', value: 'Agua' });
    const second = queue.record('validation_started');
    await Promise.all([first, second, queue.flush()]);
    assert.equal(calls[0], 'start');
    assert.equal(calls[1].value, 'Agua');
    assert.equal(calls[2].action, 'validation_started');
    assert.notEqual(calls[1].eventId, calls[2].eventId);
    await queue.record('cancelled');
    assert.equal(calls.filter((item) => item === 'start').length, 1);
});

test('retries with the same event identifier to avoid duplicate records', async () => {
    const ids = [];
    const queue = createCaptureAuditQueue({
        start: async () => {}, wait: async () => {},
        send: async (event) => {
            ids.push(event.eventId);
            if (ids.length < 3) throw new Error('network');
        },
    });
    await queue.record('click', { label: 'Añadir' });
    assert.equal(ids.length, 3);
    assert.equal(new Set(ids).size, 1);
});

test('retains failed movements and does not send later ones ahead of them', async () => {
    let offline = true;
    const calls = [];
    const queue = createCaptureAuditQueue({
        start: async () => {}, wait: async () => {},
        send: async (event) => {
            if (offline) throw new Error('network');
            calls.push(event.action);
        },
    });
    await assert.rejects(queue.record('file_selected'), /network/);
    offline = false;
    await queue.record('cancelled');
    assert.deepEqual(calls, ['file_selected', 'cancelled']);
});

test('authentication errors are not repeatedly retried', async () => {
    let calls = 0;
    const queue = createCaptureAuditQueue({
        start: async () => { calls += 1; throw Object.assign(new Error('auth'), { status: 401 }); },
        send: async () => {}, wait: async () => {},
    });
    await assert.rejects(queue.flush());
    assert.equal(calls, 1);
});

test('UUID generation also works on an HTTP virtual machine without randomUUID', () => {
    const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: {
        getRandomValues: (array) => { array.fill(7); return array; },
    } });
    try {
        assert.match(newAuditId(), /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/);
    } finally {
        Object.defineProperty(globalThis, 'crypto', original);
    }
});
