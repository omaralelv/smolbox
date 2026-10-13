import assert from 'node:assert/strict';
import { test } from 'node:test';
import { obtenerAlertaDevolucionPersistida } from '../src/lib/reimbursementReturnAlert.js';

test('shows a treasury return as returned for management without browser-local metadata', () => {
    assert.deepEqual(
        obtenerAlertaDevolucionPersistida({
            backendStatus: 'accounting_manager_review',
            correctionReturnStatus: 'accounting_manager_review',
        }, 'gerencia'),
        { tieneEstadoPersistido: true, esDevuelto: true, esResuelto: false }
    );
});

test('shows a manager return as returned for accounting without browser-local metadata', () => {
    assert.deepEqual(
        obtenerAlertaDevolucionPersistida({
            backendStatus: 'under_accounting_review',
            correctionReturnStatus: 'under_accounting_review',
        }, 'contabilidad'),
        { tieneEstadoPersistido: true, esDevuelto: true, esResuelto: false }
    );
});

test('shows a direction return as returned for treasury without browser-local metadata', () => {
    assert.deepEqual(
        obtenerAlertaDevolucionPersistida({
            backendStatus: 'treasury_review',
            correctionReturnStatus: 'treasury_review',
        }, 'tesoreria'),
        { tieneEstadoPersistido: true, esDevuelto: true, esResuelto: false }
    );
});

test('shows the request as resolved for treasury after management resends it', () => {
    assert.deepEqual(
        obtenerAlertaDevolucionPersistida({
            backendStatus: 'treasury_review',
            correctionReturnStatus: 'accounting_manager_review',
        }, 'tesoreria'),
        { tieneEstadoPersistido: true, esDevuelto: false, esResuelto: true }
    );
});

test('preserves the resolved management state after accounting resubmits', () => {
    assert.deepEqual(
        obtenerAlertaDevolucionPersistida({
            backendStatus: 'accounting_manager_review',
            correctionReturnStatus: 'under_accounting_review',
        }, 'gerencia'),
        { tieneEstadoPersistido: true, esDevuelto: false, esResuelto: true }
    );
});

test('uses existing browser metadata only when the backend has no return status', () => {
    assert.equal(
        obtenerAlertaDevolucionPersistida({ backendStatus: 'accounting_manager_review' }, 'gerencia')
            .tieneEstadoPersistido,
        false
    );
});
