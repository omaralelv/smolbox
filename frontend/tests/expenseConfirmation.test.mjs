import assert from 'node:assert/strict';
import test from 'node:test';

import { requiresExpenseConfirmation } from '../src/lib/expenseConfirmation.js';

const invoice = {
    documentType: 'factura', amount: '100.00', date: '2026-08-07',
    fiscalUuid: '99999999-9999-4999-8999-999999999999',
    documentAmount: '100.00', documentDate: '2026-08-07',
    documentFiscalUuid: '99999999-9999-4999-8999-999999999999',
};

test('matching invoice fields do not require the additional confirmation', () => {
    assert.equal(requiresExpenseConfirmation(invoice), false);
    assert.equal(requiresExpenseConfirmation({ ...invoice, amount: 100, documentAmount: '100.000' }), false);
    assert.equal(requiresExpenseConfirmation({ ...invoice, amount: 0, documentAmount: 0 }), false);
});

test('each individual mismatch requires confirmation, including a manually changed fiscal UUID', () => {
    for (const change of [
        { amount: '100.01' }, { date: '2026-08-08' },
        { fiscalUuid: 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA' },
    ]) assert.equal(requiresExpenseConfirmation({ ...invoice, ...change }), true);
});

test('missing or unreadable document fields are not considered matches', () => {
    for (const field of ['documentAmount', 'documentDate', 'documentFiscalUuid']) {
        for (const value of [null, undefined, '']) {
            assert.equal(requiresExpenseConfirmation({ ...invoice, [field]: value }), true, field);
        }
    }
    for (const documentAmount of ['unreadable', Infinity, NaN]) {
        assert.equal(requiresExpenseConfirmation({ ...invoice, documentAmount }), true);
    }
});

test('amounts use the existing two-decimal rounding rule', () => {
    assert.equal(requiresExpenseConfirmation({ ...invoice, amount: '0.30', documentAmount: 0.1 + 0.2 }), false);
    assert.equal(requiresExpenseConfirmation({ ...invoice, amount: '100.004' }), false);
    assert.equal(requiresExpenseConfirmation({ ...invoice, amount: '100.006' }), true);
});

test('vale and recibo compare only date and amount, without requiring fiscal UUIDs', () => {
    for (const documentType of ['vale', 'recibo']) {
        const receipt = { ...invoice, documentType, fiscalUuid: null, documentFiscalUuid: null };
        assert.equal(requiresExpenseConfirmation(receipt), false);
        assert.equal(requiresExpenseConfirmation({ ...receipt, date: '2026-08-08' }), true);
        assert.equal(requiresExpenseConfirmation({ ...receipt, documentAmount: null }), true);
        assert.equal(requiresExpenseConfirmation({ ...receipt, documentDate: null }), true);
    }
});

test('incomplete entered data or an unknown document type cannot bypass confirmation', () => {
    for (const change of [{ amount: '' }, { date: null }, { fiscalUuid: null }, { documentType: 'other' }]) {
        assert.equal(requiresExpenseConfirmation({ ...invoice, ...change }), true);
    }
});
