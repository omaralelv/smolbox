import assert from 'node:assert/strict';
import test from 'node:test';

import { requestAgeDisplay, shouldRefreshRequestAges } from '../src/lib/requestAge.js';

const request = {
    backendStatus: 'submitted', firstSubmittedAt: '2026-10-23T18:00:00Z', elapsedDays: 5,
};

test('the server supplies the count and the last submission or invoice date cannot reset it', () => {
    const result = requestAgeDisplay({ ...request, fecha: '28/10/2026', submittedAt: '2026-10-28T12:00:00Z' });
    assert.equal(result.label, '5');
    assert.ok(result.title.includes('23/10/2026'));
    assert.equal(requestAgeDisplay({ ...request, elapsedDays: 0 }).label, '0');
    assert.ok(requestAgeDisplay({ ...request, elapsedDays: 1 }).title.includes('1 d\u00eda natural'));
});

test('timestamps in tooltips use Mexico City dates instead of the browser timezone', () => {
    assert.ok(requestAgeDisplay({ ...request, firstSubmittedAt: '2026-10-24T04:00:00Z' })
        .title.includes('23/10/2026'));
});

test('terminal requests show the frozen count only if the stop date is known', () => {
    for (const backendStatus of ['paid', 'closed', 'rejected']) {
        const stopped = { ...request, backendStatus, ageStoppedAt: '2026-10-28T18:00:00Z' };
        assert.equal(requestAgeDisplay(stopped).label, '5');
        assert.ok(requestAgeDisplay(stopped).title.includes('Contador detenido'));
        assert.equal(requestAgeDisplay({ ...stopped, ageStoppedAt: null }).label, 'Sin fecha');
    }
});

test('legacy caches and missing or invalid counts do not invent dates or zero days', () => {
    for (const data of [null, {}, { fecha: '23/10/2026' }, { ...request, firstSubmittedAt: null },
        ...[null, undefined, -1, 1.5, '5', NaN, Infinity].map((elapsedDays) => ({ ...request, elapsedDays }))]) {
        assert.equal(requestAgeDisplay(data).label, 'Sin fecha');
    }
    assert.equal(requestAgeDisplay({ ...request, backendStatus: 'draft' }).label, 'Sin enviar');
});

test('the daily refresh uses server time and monotonic elapsed time, not the computer clock', () => {
    assert.equal(shouldRefreshRequestAges('2026-10-28T05:59:30Z', 29_999), false);
    assert.equal(shouldRefreshRequestAges('2026-10-28T05:59:30Z', 30_000), true);
    assert.equal(shouldRefreshRequestAges('2026-10-28T23:59:30Z', 60_000), false);
    assert.equal(shouldRefreshRequestAges('2026-10-28T06:00:00Z', 86_400_000), true);
    for (const value of [null, undefined, '', 'bad-date']) {
        assert.equal(shouldRefreshRequestAges(value, 60_000), false);
    }
    assert.equal(shouldRefreshRequestAges('2026-10-28T05:59:30Z', -1), false);
});
