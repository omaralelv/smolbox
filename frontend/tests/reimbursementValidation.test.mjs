import assert from 'node:assert/strict';
import { test } from 'node:test';
import { accountingReadinessBlockers } from '../src/lib/reimbursementValidation.js';

test('reports total mismatch and names the expense with missing authorization', () => {
    const blockers = accountingReadinessBlockers({
        ready_for_accounting_approval: false,
        expense_count: 1,
        reported_total: '100.00',
        calculated_total: '125.00',
        difference: '25.00',
        missing_authorization_expense_ids: ['expense-1'],
        missing_cfdi_expense_ids: [],
        invalid_cfdi_expense_ids: [],
        duplicate_cfdi_uuids: [],
        issues: [
            { code: 'reported_total_mismatch', severity: 'error' },
            { code: 'missing_authorization', severity: 'warning' },
        ],
    }, [
        {
            backendId: 'expense-1',
            nombre: 'Papelería',
            monto: 125,
        },
    ]);

    assert.equal(blockers.length, 2);
    assert.match(blockers[0], /total reportado/);
    assert.match(blockers[1], /Papelería/);
    assert.match(blockers[1], /expense-1/);
});

test('does not treat a receipt warning as an accounting blocker', () => {
    const blockers = accountingReadinessBlockers({
        ready_for_accounting_approval: false,
        expense_count: 1,
        reported_total: '100.00',
        calculated_total: '100.00',
        difference: '0.00',
        missing_authorization_expense_ids: [],
        missing_cfdi_expense_ids: ['expense-1'],
        invalid_cfdi_expense_ids: [],
        duplicate_cfdi_uuids: [],
        issues: [
            { code: 'missing_receipts', severity: 'warning' },
            { code: 'missing_cfdi_xml', severity: 'warning' },
        ],
    }, [{ backendId: 'expense-1', nombre: 'Alimentos' }]);

    assert.equal(blockers.length, 1);
    assert.match(blockers[0], /evidencia fiscal válida/);
    assert.doesNotMatch(blockers[0], /recibo/);
});

test('returns no blockers when accounting readiness is true', () => {
    assert.deepEqual(
        accountingReadinessBlockers({ ready_for_accounting_approval: true }),
        []
    );
});
