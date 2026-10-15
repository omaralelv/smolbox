import assert from 'node:assert/strict';
import test from 'node:test';
import { combinarHistorialObservaciones, historialDesdeEventos, historialParaGasto, mensajeErrorHistorial, observacionInicialDesdeGasto, puedeAgregarObservacion } from '../src/lib/observationHistory.js';

const initial = observacionInicialDesdeGasto({ backendId: 'expense-1', observaciones: 'Nota inicial', fecha: '2026-08-07' });
function event(id, message = 'Comentario posterior', payload = {}) {
    return { id, expense_id: 'expense-1', message, action: 'expense_observation_added',
        created_at: '2026-08-08T10:00:00Z', event_payload: { actor_role: 'authorizer', ...payload } };
}

test('preserves the initial note when another observation or edit exists for the expense', () => {
    const history = historialDesdeEventos([event('later'), { ...event('edit'), action: 'expense_review_updated' }]);
    assert.deepEqual(combinarHistorialObservaciones([initial], history).map((note) => note.id), ['init-obs-expense-1', 'edit', 'later']);
});

test('deduplicates repeated event IDs but preserves identical text from distinct events', () => {
    const history = historialDesdeEventos([event('one', 'Igual'), event('one', 'Igual'), event('two', 'Igual')]);
    const result = combinarHistorialObservaciones([initial], history);
    assert.equal(result.length, 3);
    assert.equal(result.filter((note) => note.texto === 'Igual').length, 2);
});

test('uses the persisted initial event instead of the synthetic initial note', () => {
    const history = historialDesdeEventos([event('initial', 'Nota inicial', { is_initial_observation: true, actor_role: 'admin' }), event('later')]);
    const result = combinarHistorialObservaciones([initial], history);
    assert.equal(result.length, 2);
    assert.equal(result[0].visibilidad, 'PUBLIC');
    assert.equal(result.filter((note) => note.texto === 'Nota inicial').length, 1);
});

test('recognizes matching legacy imported initial notes, not unrelated comments', () => {
    const history = historialDesdeEventos([event('legacy', 'Nota inicial', { source: 'frontend_draft' }), event('later')]);
    assert.equal(combinarHistorialObservaciones([initial], history).length, 2);
    assert.equal(combinarHistorialObservaciones([initial], historialDesdeEventos([event('later', 'Nota inicial')])).length, 2);
});

test('retains partition actions and visibility rules while excluding click events', () => {
    const events = ['expense_partitioned', 'expense_partition_updated', 'expense_partition_cancelled'].map((action) => ({
        ...event(action, action, { actor_role: 'accountant' }), action,
    }));
    const history = historialDesdeEventos([...events, { ...event('click'), action: 'ui_click' },
        { ...event('rejected', 'Motivo', { actor_role: 'accountant' }), action: 'expense_authorization_rejected' }]);
    assert.equal(history.length, 4);
    assert.equal(history.filter((note) => note.visibilidad === 'INTERNO').length, 3);
    assert.equal(history.find((note) => note.id === 'rejected').texto, 'Gasto no autorizado. Motivo: "Motivo"');
});

test('retains all 225 observations after merging overlapping pages', () => {
    const records = Array.from({ length: 225 }, (_, index) => event(String(index)));
    const history = combinarHistorialObservaciones([initial], historialDesdeEventos([...records, ...records.slice(0, 5)]));
    assert.equal(history.length, 226);
});

test('automatic partition descriptions are system records dated by creation, not invoice date', () => {
    const description = observacionInicialDesdeGasto({ backendId: 'child', idOriginal: 'parent', esHijoParticion: true,
        observaciones: 'Partici\u00f3n 1/2 del gasto Gasto - Agua.', fecha: '2026-09-03', createdAt: '2026-10-15T18:13:00Z' });
    assert.equal(description.autor, 'SISTEMA');
    assert.equal(description.rol, 'sistema');
    assert.equal(description.tipo, 'sistema');
    assert.equal(description.fechaTimestamp, Date.parse('2026-10-15T18:13:00Z'));
    assert.equal(initial.fecha, 'Fecha no disponible');
    assert.equal(initial.fechaTimestamp, 0);
    assert.equal(initial.autor, 'OBSERVACI\u00d3N INICIAL', 'do not invent an author when historical metadata is missing');
});

test('partition history identifies inherited notes without mixing siblings or leaking private notes', () => {
    const history = historialDesdeEventos([
        { ...event('parent'), expense_id: 'parent' },
        { ...event('child'), expense_id: 'child' },
        { ...event('sibling'), expense_id: 'sibling' },
        { ...event('private', 'Internal note', { actor_role: 'accountant' }), expense_id: 'parent' },
    ]);
    const expense = { backendId: 'child', idOriginal: 'parent' };
    assert.deepEqual(historialParaGasto(history, expense, 'tienda').map((note) => [note.id, note.origen]), [
        ['child', 'Esta partici\u00f3n'], ['parent', 'Gasto original'],
    ]);
    assert.equal(historialParaGasto(history, expense, 'tesoreria').length, 3);
    assert.deepEqual(historialParaGasto(history, null, 'admin'), []);
});

test('the backend controls comment permissions, with a fallback only for unsaved local drafts', () => {
    assert.equal(puedeAgregarObservacion({ backendId: 'expense', canAddObservation: true }), true);
    assert.equal(puedeAgregarObservacion({ backendId: 'expense', canAddObservation: false }, { localDraft: true }), false);
    assert.equal(puedeAgregarObservacion({ backendId: 'expense' }, { localDraft: true }), false);
    assert.equal(puedeAgregarObservacion({ id: 1 }, { localDraft: true }), true);
    assert.equal(puedeAgregarObservacion(null), false);
});

test('a failed refresh after a successful save cannot be reported as a failed write', () => {
    assert.ok(mensajeErrorHistorial(true).startsWith('La observaci\u00f3n se guard\u00f3'));
    assert.ok(mensajeErrorHistorial(true).includes('no es necesario enviarla otra vez'));
    assert.equal(mensajeErrorHistorial(false), 'No se pudieron actualizar las observaciones. Se conserva el historial cargado.');
});
