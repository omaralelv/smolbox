const DRAFT_GASTOS_KEY = 'listaGastosSmolbox';
const DRAFT_REQUEST_KEY = 'solicitudBorradorBackendSmolbox';

const draftGastos = new Map();
const draftRequests = new Map();

export function loadDraftGastos(storeId) {
    const key = scopedKey(DRAFT_GASTOS_KEY, storeId);
    if (!key) return [];
    if (draftGastos.has(key)) return draftGastos.get(key);

    const saved = localStorage.getItem(key);
    const expenses = saved ? JSON.parse(saved) : [];
    draftGastos.set(key, expenses);
    return expenses;
}

export function addDraftGasto(gasto, storeId) {
    const gastos = loadDraftGastos(storeId);
    const exists = gastos.some((item) => item.id === gasto.id);
    const updated = exists
        ? gastos.map((item) => (item.id === gasto.id ? gasto : item))
        : [...gastos, gasto];

    saveDraftGastos(updated, storeId);
    return updated;
}

export function replaceDraftGastos(gastos, storeId) {
    const updated = Array.isArray(gastos) ? [...gastos] : [];
    saveDraftGastos(updated, storeId);
    return updated;
}

export function updateDraftGasto(gastoId, updater, storeId) {
    const updated = loadDraftGastos(storeId).map((item) => {
        const itemId = item.backendId ?? item.backend_id ?? item.id;
        return String(itemId) === String(gastoId) ? updater(item) : item;
    });

    saveDraftGastos(updated, storeId);
    return updated;
}

export function removeDraftGasto(gastoId, storeId) {
    const updated = loadDraftGastos(storeId).filter((item) => {
        const itemId = item.backendId ?? item.backend_id ?? item.id;
        return String(itemId) !== String(gastoId);
    });

    saveDraftGastos(updated, storeId);
    return updated;
}

export function clearDraftGastos(storeId) {
    const key = scopedKey(DRAFT_GASTOS_KEY, storeId);
    if (!key) return;
    draftGastos.set(key, []);
    localStorage.removeItem(key);
    clearDraftRequest(storeId);
}

export function loadDraftRequest(storeId) {
    const key = scopedKey(DRAFT_REQUEST_KEY, storeId);
    if (!key) return null;
    if (draftRequests.has(key)) return draftRequests.get(key);

    const saved = localStorage.getItem(key);
    const request = saved ? JSON.parse(saved) : null;
    draftRequests.set(key, request);
    return request;
}

export function saveDraftRequest(solicitud, storeId) {
    const key = scopedKey(DRAFT_REQUEST_KEY, storeId);
    const backendId = solicitud?.backendId || solicitud?.backend_id;
    if (!key || !backendId) return null;

    const draftRequest = {
        backendId: String(backendId),
        id: solicitud.id || null,
        folio: solicitud.folio || solicitud.id || null,
        storeId: String(storeId),
        savedAt: new Date().toISOString(),
    };
    draftRequests.set(key, draftRequest);
    localStorage.setItem(key, JSON.stringify(draftRequest));
    return draftRequest;
}

export function clearDraftRequest(storeId) {
    const key = scopedKey(DRAFT_REQUEST_KEY, storeId);
    if (!key) return;
    draftRequests.set(key, null);
    localStorage.removeItem(key);
}

function saveDraftGastos(gastos, storeId) {
    const key = scopedKey(DRAFT_GASTOS_KEY, storeId);
    if (!key) return;
    draftGastos.set(key, gastos);
    localStorage.setItem(key, JSON.stringify(gastos.map(sinArchivos)));
}

function scopedKey(base, storeId) {
    return storeId ? `${base}:${storeId}` : null;
}

function sinArchivos(gasto) {
    const copia = { ...gasto };
    delete copia.facturaFile;
    delete copia.valeFile;
    delete copia.reciboFile;
    return copia;
}
