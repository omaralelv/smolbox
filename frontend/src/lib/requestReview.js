const REVIEW_ACTIONS = [
    'start_authorization_review',
    'start_accounting_review',
    'start_accounting_manager_review',
    'start_treasury_review',
];

export function accionRevisionDisponible(solicitud) {
    return REVIEW_ACTIONS.find((accion) => solicitud?.availableActions?.includes(accion)) || null;
}

export function permiteAvanceAutorizacionAlCargar(currentRole) {
    return String(currentRole || '').toLowerCase().trim() !== 'admin';
}

export function accionInicialPorRol(currentRole, solicitud) {
    const rol = String(currentRole || '').toLowerCase().trim();
    const status = solicitud?.backendStatus || solicitud?.backend_status;

    if (rol === 'supervisor' && status === 'submitted') {
        return 'start_authorization_review';
    }
    if (rol === 'contabilidad' && ['submitted', 'authorized'].includes(status)) {
        return 'start_accounting_review';
    }
    if (rol === 'gerencia' && status === 'accounting_reviewed') {
        return 'start_accounting_manager_review';
    }
    if (rol === 'tesoreria' && status === 'accounting_manager_approved') {
        return 'start_treasury_review';
    }
    return null;
}
