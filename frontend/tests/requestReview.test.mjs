import assert from 'node:assert/strict';
import test from 'node:test';

import {
    accionInicialPorRol,
    accionRevisionDisponible,
    permiteAvanceAutorizacionAlCargar,
} from '../src/lib/requestReview.js';

const steps = [
    ['submitted', 'start_authorization_review'],
    ['submitted', 'start_accounting_review'],
    ['authorized', 'start_accounting_review'],
    ['accounting_reviewed', 'start_accounting_manager_review'],
    ['accounting_manager_approved', 'start_treasury_review'],
];

test('admin never changes the stage just by opening a request', () => {
    for (const [backendStatus, action] of steps) {
        const request = { backendStatus, availableActions: [action] };
        assert.equal(accionInicialPorRol('admin', request), null);
        assert.equal(accionInicialPorRol(' ADMIN ', request), null);
        assert.equal(accionRevisionDisponible(request), action, 'manual action remains available');
    }
});

test('manual review requires an action currently allowed by the backend', () => {
    for (const request of [null, {}, { availableActions: [] }, { availableActions: ['edit_expense'] }]) {
        assert.equal(accionRevisionDisponible(request), null);
    }
});

test('opening requests keeps the existing automatic review steps for operational roles', () => {
    for (const [role, backendStatus, action] of [
        ['supervisor', 'submitted', 'start_authorization_review'],
        ['contabilidad', 'submitted', 'start_accounting_review'],
        ['contabilidad', 'authorized', 'start_accounting_review'],
        ['gerencia', 'accounting_reviewed', 'start_accounting_manager_review'],
        ['tesoreria', 'accounting_manager_approved', 'start_treasury_review'],
    ]) {
        assert.equal(accionInicialPorRol(role, { backendStatus }), action);
        assert.equal(accionInicialPorRol(role, { backend_status: backendStatus }), action);
        assert.equal(accionInicialPorRol(role, { backendStatus: 'paid' }), null);
    }
});

test('non-review roles and closed requests do not gain an automatic action', () => {
    for (const role of ['tienda', 'direccion', '', null]) {
        assert.equal(accionInicialPorRol(role, { backendStatus: 'submitted' }), null);
    }
    assert.equal(accionInicialPorRol('admin', null), null);
});

test('admin cannot auto-complete authorization by loading or refreshing its list', () => {
    for (const role of ['admin', ' ADMIN ']) {
        assert.equal(permiteAvanceAutorizacionAlCargar(role), false);
    }
    assert.equal(permiteAvanceAutorizacionAlCargar('supervisor'), true);
});
