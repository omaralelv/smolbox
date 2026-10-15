import { PUEDE_LEER_OBSERVACION, VISIBILIDAD } from '../components/shared/roles.js';

const ACTIONS = new Set([
    'expense_observation_added', 'expense_removed_from_request', 'expense_review_updated',
    'expense_authorization_rejected', 'expense_partitioned', 'expense_partition_updated',
    'expense_partition_cancelled',
]);
const PUBLIC_ACTIONS = new Set(['expense_removed_from_request', 'expense_authorization_rejected']);
const ROLES = {
    store: 'tienda', authorizer: 'supervisor', accountant: 'contabilidad',
    accounting_manager: 'gerencia', treasury: 'tesoreria', director: 'direccion', admin: 'admin',
};

function fechaLegible(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export function observacionInicialDesdeGasto(expense) {
    const text = String(expense.observaciones || expense.observacion || '').trim();
    if (!text) return null;
    const expenseId = expense.backendId ?? expense.backend_id ?? expense.id;
    // The invoice date is not the timestamp of an observation or partition.
    const date = expense.created_at || expense.createdAt;
    const systemDescription = Boolean(expense.esHijoParticion || expense.es_hijo_particion || parentExpenseId(expense));
    return {
        id: `init-obs-${expenseId}`, gastoId: expenseId,
        autor: systemDescription ? 'SISTEMA' : 'OBSERVACI\u00d3N INICIAL', rol: 'sistema',
        texto: text, fecha: date ? fechaLegible(date) : 'Fecha no disponible', fechaTimestamp: Date.parse(date || '') || 0,
        visibilidad: VISIBILIDAD.PUBLIC,
        tipo: systemDescription ? 'sistema' : 'inicial',
    };
}

export function historialDesdeEventos(events = []) {
    return events.map((event) => {
        const payload = event.event_payload || event.payload || {};
        const expenseId = event.expense_id || event.expenseId || payload.expense_id || payload.expenseId;
        if (!ACTIONS.has(event.action) || !expenseId || !event.message) return null;
        const backendRole = String(payload.actor_role || event.actor_role || '').toLowerCase().trim();
        const role = ROLES[backendRole] || backendRole || 'sistema';
        const author = role.toUpperCase();
        let text = event.message;
        if (event.action === 'expense_removed_from_request') text = `Gasto eliminado por ${author}. Motivo: "${text}"`;
        if (event.action === 'expense_authorization_rejected') text = `Gasto no autorizado. Motivo: "${text}"`;
        const timestamp = Number(payload.fecha_timestamp || payload.fechaTimestamp || 0);
        const date = event.created_at || event.createdAt;
        const initial = payload.is_initial_observation === true;
        return {
            id: event.id, gastoId: expenseId, autor: author, rol: role, texto: text,
            fecha: fechaLegible(date),
            fechaTimestamp: Number.isFinite(timestamp) && timestamp > 0
                ? (timestamp > 10_000_000_000 ? timestamp : timestamp * 1000)
                : Date.parse(date || '') || 0,
            visibilidad: initial || PUBLIC_ACTIONS.has(event.action) || ['tienda', 'supervisor'].includes(role)
                ? VISIBILIDAD.PUBLIC : VISIBILIDAD.INTERNO,
            esInicial: initial, source: payload.source,
            tipo: initial ? 'inicial' : event.action === 'expense_observation_added' ? 'comentario' : 'movimiento',
        };
    }).filter(Boolean).sort(compareObservations);
}

export function combinarHistorialObservaciones(initial = [], events = []) {
    const remaining = initial.filter((note) => !events.some((event) => (
        String(event.gastoId) === String(note.gastoId)
        && (event.esInicial || (event.source === 'frontend_draft' && event.texto.trim() === note.texto.trim()))
    )));
    // Repeated text can be intentional; only repeated event identifiers are duplicates.
    const unique = new Map([...remaining, ...events].map((note) => [String(note.id), note]));
    return [...unique.values()].sort(compareObservations);
}

function parentExpenseId(expense) {
    return expense?.idOriginal ?? expense?.id_original ?? expense?.partition_parent_expense_id ?? null;
}

export function historialParaGasto(history, expense, role) {
    if (!expense) return [];
    const expenseId = expense.backendId ?? expense.backend_id ?? expense.id;
    const parentId = parentExpenseId(expense);
    const relatedIds = [expenseId, parentId].filter((id) => id !== null && id !== undefined).map(String);
    return history.filter((note) => relatedIds.includes(String(note.gastoId)) && PUEDE_LEER_OBSERVACION(role, note.visibilidad))
        .map((note) => ({
            ...note,
            origen: parentId ? (String(note.gastoId) === String(parentId) ? 'Gasto original' : 'Esta partici\u00f3n') : null,
        }));
}

export function puedeAgregarObservacion(expense, { localDraft = false } = {}) {
    if (!expense) return false;
    const permission = expense.canAddObservation ?? expense.can_add_observation;
    if (typeof permission === 'boolean') return permission;
    return localDraft && !expense.backendId && !expense.backend_id;
}

export function mensajeErrorHistorial(observacionGuardada = false) {
    return observacionGuardada
        ? 'La observaci\u00f3n se guard\u00f3, pero no se pudo actualizar el historial. Reintenta la consulta; no es necesario enviarla otra vez.'
        : 'No se pudieron actualizar las observaciones. Se conserva el historial cargado.';
}

function compareObservations(left, right) {
    return (left.fechaTimestamp || 0) - (right.fechaTimestamp || 0)
        || String(left.id).localeCompare(String(right.id));
}
