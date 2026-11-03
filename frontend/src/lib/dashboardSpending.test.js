import assert from 'node:assert/strict';
import test from 'node:test';
import { filterSpendingRows, hasSpendingBreakdown } from './dashboardSpending.js';

const rows = [
    { storeId: 'a', values: { 2025: 120, 2026: 280 }, normalValues: { 2025: 100, 2026: 250 }, extemporaneousValues: { 2025: 20, 2026: 30 } },
    { storeId: 'b', values: { 2025: 50, 2026: 90 }, normalValues: { 2025: 50, 2026: 80 }, extemporaneousValues: { 2025: 0, 2026: 10 } },
];

test('all keeps the existing totals, and source filters add back to those totals', () => {
    assert.equal(filterSpendingRows(rows), rows);
    const normal = filterSpendingRows(rows, 'all', 'normal');
    const archive = filterSpendingRows(rows, 'all', 'extemporaneous');
    for (let index = 0; index < rows.length; index += 1) {
        for (const year of [2025, 2026]) {
            assert.equal(normal[index].values[year] + archive[index].values[year], rows[index].values[year]);
        }
    }
    assert.equal(rows[0].values[2026], 280);
});

test('source and store filters combine, including zero amounts and empty results', () => {
    assert.deepEqual(filterSpendingRows(rows, 'b', 'extemporaneous').map((row) => row.values), [{ 2025: 0, 2026: 10 }]);
    assert.deepEqual(filterSpendingRows(rows, 'a', 'normal').map((row) => row.values), [{ 2025: 100, 2026: 250 }]);
    assert.deepEqual(filterSpendingRows(rows, 'missing'), []);
    assert.deepEqual(filterSpendingRows([], 'all', 'extemporaneous'), []);
    assert.throws(() => filterSpendingRows(rows, 'all', 'unknown'));
});

test('an older backend without the breakdown cannot enable an inaccurate source filter', () => {
    assert.ok(hasSpendingBreakdown(rows, [2025, 2026]));
    assert.equal(hasSpendingBreakdown([{ storeId: 'old', values: { 2026: 50 } }], [2026]), false);
    assert.equal(hasSpendingBreakdown([{ ...rows[0], extemporaneousValues: {} }], [2026]), false);
});
