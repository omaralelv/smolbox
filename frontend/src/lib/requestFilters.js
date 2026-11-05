const ROLES_WITH_REQUEST_FILTERS = new Set([
    'contabilidad',
    'gerencia',
    'tesoreria',
    'direccion',
    'admin',
]);

export function puedeFiltrarSolicitudes(currentRole) {
    return ROLES_WITH_REQUEST_FILTERS.has(String(currentRole || '').toLowerCase().trim());
}

export function obtenerFechaSolicitud(solicitud) {
    return solicitud?.fecha
        || solicitud?.fechaEnvio
        || solicitud?.fecha_envio
        || solicitud?.createdAt
        || solicitud?.created_at
        || '';
}

export function normalizarFechaSolicitud(fecha) {
    const valor = String(fecha || '').trim();
    const fechaLatina = valor.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (fechaLatina) {
        return `${fechaLatina[3]}-${fechaLatina[2]}-${fechaLatina[1]}`;
    }

    const fechaIso = valor.slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(fechaIso) ? fechaIso : '';
}
