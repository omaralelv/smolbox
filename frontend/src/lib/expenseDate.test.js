import assert from 'node:assert/strict';
import test from 'node:test';

import { formatoFechaGasto } from './expenseDate.js';

test('formats ISO dates as Mexican dates without timezone conversion', () => {
    assert.equal(formatoFechaGasto('2026-08-07'), '07/08/2026');
    assert.equal(formatoFechaGasto('2026-08-07T00:00:00Z'), '07/08/2026');
});

test('preserves and zero-pads Mexican date strings', () => {
    assert.equal(formatoFechaGasto('7/8/2026'), '07/08/2026');
});

test('uses an em dash when date is missing or invalid', () => {
    assert.equal(formatoFechaGasto(null), '—');
    assert.equal(formatoFechaGasto('not-a-date'), '—');
});
