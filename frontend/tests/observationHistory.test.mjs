import assert from 'node:assert/strict';
import test from 'node:test';
import { combinarHistorialObservaciones, historialDesdeEventos, observacionInicialDesdeGasto } from '../src/lib/observationHistory.js';

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
