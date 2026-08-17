const DRAFT_GASTOS_KEY = 'listaGastosSmolbox';

let draftGastos = null;

export function loadDraftGastos() {
    if (draftGastos) return draftGastos;

    const guardados = localStorage.getItem(DRAFT_GASTOS_KEY);
    draftGastos = guardados ? JSON.parse(guardados) : [];
    return draftGastos;
}

export function addDraftGasto(gasto) {
    const gastos = loadDraftGastos();
    const existe = gastos.some((item) => item.id === gasto.id);
    draftGastos = existe ? gastos : [...gastos, gasto];
    persistDraftMetadata();
    return draftGastos;
}

export function clearDraftGastos() {
    draftGastos = [];
    localStorage.removeItem(DRAFT_GASTOS_KEY);
    localStorage.removeItem('pendienteGasto');
}

function persistDraftMetadata() {
    localStorage.setItem(DRAFT_GASTOS_KEY, JSON.stringify(draftGastos.map(sinArchivos)));
}

function sinArchivos(gasto) {
    const copia = { ...gasto };
    delete copia.facturaFile;
    delete copia.valeFile;
    return copia;
}
