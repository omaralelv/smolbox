const DRAFT_GASTOS_KEY = 'listaGastosSmolbox';
const DRAFT_REQUEST_KEY = 'solicitudBorradorBackendSmolbox';

let draftGastos = null;
let draftRequest = null;

export function loadDraftGastos() {
    if (draftGastos) return draftGastos;

    const guardados = localStorage.getItem(DRAFT_GASTOS_KEY);
    draftGastos = guardados ? JSON.parse(guardados) : [];
    return draftGastos;
}

export function addDraftGasto(gasto) {
    const gastos = loadDraftGastos();
    const existe = gastos.some((item) => item.id === gasto.id);
    //draftGastos = existe ? gastos : [...gastos, gasto];
    if (existe) {
        // 🔄 Si existe, actualizamos el gasto con los nuevos datos (incluyendo observaciones)
        draftGastos = gastos.map((item) => (item.id === gasto.id ? gasto : item));
    } else {
        // ➕ Si no existe, lo agregamos a la lista
        draftGastos = [...gastos, gasto];
    }

    persistDraftMetadata();
    return draftGastos;
}

export function replaceDraftGastos(gastos) {
    draftGastos = Array.isArray(gastos) ? [...gastos] : [];
    persistDraftMetadata();
    return draftGastos;
}

export function updateDraftGasto(gastoId, updater) {
    const gastos = loadDraftGastos();
    draftGastos = gastos.map((item) => {
        const itemId = item.backendId ?? item.backend_id ?? item.id;
        if (String(itemId) !== String(gastoId)) return item;
        return updater(item);
    });

    persistDraftMetadata();
    return draftGastos;
}

export function clearDraftGastos() {
    draftGastos = [];
    localStorage.removeItem(DRAFT_GASTOS_KEY);
    localStorage.removeItem('pendienteGasto');
    clearDraftRequest();
}

export function loadDraftRequest() {
    if (draftRequest) return draftRequest;

    const guardado = localStorage.getItem(DRAFT_REQUEST_KEY);
    draftRequest = guardado ? JSON.parse(guardado) : null;
    return draftRequest;
}

export function saveDraftRequest(solicitud) {
    const backendId = solicitud?.backendId || solicitud?.backend_id;
    if (!backendId) return null;

    draftRequest = {
        backendId: String(backendId),
        id: solicitud.id || null,
        folio: solicitud.folio || solicitud.id || null,
        savedAt: new Date().toISOString(),
    };
    localStorage.setItem(DRAFT_REQUEST_KEY, JSON.stringify(draftRequest));
    return draftRequest;
}

export function clearDraftRequest() {
    draftRequest = null;
    localStorage.removeItem(DRAFT_REQUEST_KEY);
}

function persistDraftMetadata() {
    localStorage.setItem(DRAFT_GASTOS_KEY, JSON.stringify(draftGastos.map(sinArchivos)));
}

function sinArchivos(gasto) {
    const copia = { ...gasto };
    delete copia.facturaFile;
    delete copia.valeFile;
    delete copia.reciboFile;
    return copia;
}
