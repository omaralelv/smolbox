import assert from 'node:assert/strict';
import test from 'node:test';
import { combinarHistorialObservaciones, historialDesdeEventos, historialParaGasto, mensajeErrorHistorial, observacionInicialDesdeGasto, puedeAgregarObservacion } from '../src/lib/observationHistory.js';

const initial = observacionInicialDesdeGasto({ backendId: 'expense-1', observaciones: 'Nota inicial', fecha: '2026-08-07' });
function event(id, message = 'Comentario posterior', payload = {}) {
    return { id, expense_id: 'expense-1', message, action: 'expense_observation_added',
        created_at: '2026-08-08T10:00:00Z', event_payload: { actor_role: 'authorizer', ...payload } };
}

test('shows two names for the same role without changing text, permissions or deduplication', () => {
    const events = [
        event('ana', 'Igual', { actor_role: 'accountant', actor_name: 'Ana Lopez' }),
        event('luis', 'Igual', { actor_role: 'accountant', actor_name: 'Luis Garcia' }),
    ];
    const history = combinarHistorialObservaciones([], historialDesdeEventos([...events, events[0]]));
    assert.deepEqual(history.map((note) => note.autor), ['Ana Lopez (CONTABILIDAD)', 'Luis Garcia (CONTABILIDAD)']);
    assert.ok(history.every((note) => note.rol === 'contabilidad' && note.visibilidad === 'INTERNO' && note.texto === 'Igual'));
    assert.deepEqual(historialParaGasto(history, { backendId: 'expense-1' }, 'tienda'), []);
    assert.equal(historialParaGasto(history, { backendId: 'expense-1' }, 'contabilidad').length, 2);
});

test('prefers the captured author name, with the server lookup as a legacy fallback', () => {
    const history = historialDesdeEventos([
        { ...event('saved', 'Nuevo', { actor_name: 'Nombre original' }), actor_name: 'Nombre cambiado' },
        { ...event('legacy'), actor_name: 'Nombre anterior disponible' },
    ]);
    assert.equal(history.find((note) => note.id === 'saved').autor, 'Nombre original (SUPERVISOR)');
    assert.equal(history.find((note) => note.id === 'legacy').autor, 'Nombre anterior disponible (SUPERVISOR)');
});

test('does not invent missing authors or trust browser-provided author metadata', () => {
    const history = historialDesdeEventos([
        { ...event('unknown', 'Sin autor', { frontend_author: 'Nombre falso', actor_name: ' ' }), actor_type: 'user' },
        { ...event('system', 'Automatico'), actor_type: 'system' },
        { ...event('without-role'), event_payload: {}, actor_type: 'user' },
    ]);
    assert.equal(history.find((note) => note.id === 'unknown').autor, 'Usuario no disponible (SUPERVISOR)');
    assert.equal(history.find((note) => note.id === 'system').autor, 'SISTEMA');
    assert.equal(history.find((note) => note.id === 'without-role').autor, 'Usuario no disponible');
    const removal = historialDesdeEventos([{ ...event('removed', 'Motivo', { actor_role: 'store', actor_name: 'Ana' }), action: 'expense_removed_from_request' }]);
    assert.equal(removal[0].autor, 'Ana (TIENDA)');
    assert.equal(removal[0].texto, 'Gasto eliminado por TIENDA. Motivo: "Motivo"');
});

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
        { ...event('parent', 'Original', { actor_name: 'Autora original' }), expense_id: 'parent' },
        { ...event('child', 'Particion', { actor_name: 'Autora particion' }), expense_id: 'child' },
        { ...event('sibling'), expense_id: 'sibling' },
        { ...event('private', 'Internal note', { actor_role: 'accountant' }), expense_id: 'parent' },
    ]);
    const expense = { backendId: 'child', idOriginal: 'parent' };
    assert.deepEqual(historialParaGasto(history, expense, 'tienda').map((note) => [note.id, note.origen]), [
        ['child', 'Esta partici\u00f3n'], ['parent', 'Gasto original'],
    ]);
    assert.equal(historialParaGasto(history, expense, 'tesoreria').length, 3);
    assert.deepEqual(historialParaGasto(history, expense, 'tienda').map((note) => note.autor), [
        'Autora particion (SUPERVISOR)', 'Autora original (SUPERVISOR)',
    ]);
    assert.deepEqual(historialParaGasto(history, null, 'admin'), []);
});

test('the backend controls comment permissions, with a fallback only for unsaved local drafts', () => {
    assert.equal(puedeAgregarObservacion({ backendId: 'expense', canAddObservation: true }), true);
    assert.equal(puedeAgregarObservacion({ backendId: 'expense', canAddObservation: false }, { localDraft: true }), false);
    assert.equal(puedeAgregarObservacion({ backendId: 'expense' }, { localDraft: true }), false);
    assert.equal(puedeAgregarObservacion({ id: 1 }, { localDraft: true }), true);
    assert.equal(puedeAgregarObservacion(null), false);
});

test('archived partition comments remain visible without mixing active siblings or private notes', () => {
    const records = [
        { ...event('own'), expense_id: 'current' },
        { ...event('active-sibling'), expense_id: 'sibling', expense_parent_id: 'parent' },
        { ...event('old'), expense_id: 'old-child', expense_parent_id: 'parent', expense_archived: true,
            expense_partition_index: 2, expense_partition_count: 3 },
        { ...event('private-old', 'Private', { actor_role: 'accountant' }), expense_id: 'old-child',
            expense_parent_id: 'parent', expense_archived: true },
        { ...event('unrelated'), expense_id: 'unrelated', expense_parent_id: 'another', expense_archived: true },
    ];
    const history = historialDesdeEventos(records);
    const child = { backendId: 'current', idOriginal: 'parent' };
    assert.deepEqual(historialParaGasto(history, child, 'tienda').map((note) => note.id), ['old', 'own']);
    assert.equal(historialParaGasto(history, child, 'tienda')[0].origen, 'Partición anterior 2/3');
    assert.equal(historialParaGasto(history, child, 'contabilidad').length, 3);
    assert.deepEqual(historialParaGasto(history, { backendId: 'parent' }, 'tienda').map((note) => note.id), ['old']);
    assert.equal(combinarHistorialObservaciones([], historialDesdeEventos([...records, ...records])).length, 5);
});

test('a failed refresh after a successful save cannot be reported as a failed write', () => {
    assert.ok(mensajeErrorHistorial(true).startsWith('La observaci\u00f3n se guard\u00f3'));
    assert.ok(mensajeErrorHistorial(true).includes('no es necesario enviarla otra vez'));
    assert.equal(mensajeErrorHistorial(false), 'No se pudieron actualizar las observaciones. Se conserva el historial cargado.');
});
