import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
    obtenerAlertaDevolucionPersistida,
    obtenerPrioridadBandeja,
} from '../src/lib/reimbursementReturnAlert.js';

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

test('prioritizes accounting requests as returned, resolved, own, single, then someone else', () => {
    assert.deepEqual(
        [
            obtenerPrioridadBandeja('contabilidad', { esDevuelto: true, esResuelto: false, queueStatus: 'taken_other' }),
            obtenerPrioridadBandeja('contabilidad', { esDevuelto: false, esResuelto: true, queueStatus: 'taken_other' }),
            obtenerPrioridadBandeja('contabilidad', { esDevuelto: false, esResuelto: false, queueStatus: 'taken' }),
            obtenerPrioridadBandeja('contabilidad', { esDevuelto: false, esResuelto: false, queueStatus: 'single' }),
            obtenerPrioridadBandeja('contabilidad', { esDevuelto: false, esResuelto: false, queueStatus: 'taken_other' }),
        ],
        [1, 2, 3, 4, 5]
    );
});

test('prioritizes resolved requests below returned for management and treasury', () => {
    for (const role of ['gerencia', 'tesoreria']) {
        assert.deepEqual(
            [
                obtenerPrioridadBandeja(role, { esDevuelto: true, esResuelto: false, queueStatus: 'taken' }),
                obtenerPrioridadBandeja(role, { esDevuelto: false, esResuelto: true, queueStatus: 'taken_other' }),
                obtenerPrioridadBandeja(role, { esDevuelto: false, esResuelto: false, queueStatus: 'taken' }),
                obtenerPrioridadBandeja(role, { esDevuelto: false, esResuelto: false, queueStatus: 'single' }),
                obtenerPrioridadBandeja(role, { esDevuelto: false, esResuelto: false, queueStatus: 'taken_other' }),
            ],
            [1, 2, 3, 3, 3]
        );
    }
});
