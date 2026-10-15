import assert from 'node:assert/strict';
import test from 'node:test';
import { createObservationSender } from '../src/lib/observationSubmission.js';

test('concurrent sends of one comment share one request and event identifier', async () => {
    const writes = [];
    const send = createObservationSender(async (expense, payload) => { writes.push({ expense, payload }); return 'saved'; }, () => 'session');
    const first = send('expense', 'Comment');
    const second = send('expense', 'Comment');
    assert.equal(first, second);
    assert.deepEqual(await Promise.all([first, second]), ['saved', 'saved']);
    assert.equal(writes.length, 1);
    assert.match(writes[0].payload.eventId, /^[a-f0-9-]{36}$/);
});

test('a network failure retains the same event identifier for retry', async () => {
    const writes = [];
    const send = createObservationSender(async (_expense, payload) => {
        writes.push(payload);
        if (writes.length === 1) throw new Error('Response lost after commit');
        return 'saved';
    }, () => 'session');
    await assert.rejects(send('expense', 'Comment'));
    assert.equal(await send('expense', 'Comment'), 'saved');
    assert.equal(writes[0].eventId, writes[1].eventId);
    await send('expense', 'Comment');
    assert.notEqual(writes[1].eventId, writes[2].eventId, 'a new intentional identical comment is not discarded');
});

test('different drafts, expenses and users never reuse another submission', async () => {
    const writes = [];
    let user = 'first';
    const send = createObservationSender(async (expense, payload) => {
        writes.push({ expense, ...payload });
        throw new Error('Offline');
    }, () => user);
    await assert.rejects(send('one', 'First'));
    await assert.rejects(send('one', 'Changed'));
    await assert.rejects(send('two', 'Changed'));
    user = 'second';
    await assert.rejects(send('one', 'Changed'));
    assert.equal(new Set(writes.map((write) => write.eventId)).size, 4);
});
