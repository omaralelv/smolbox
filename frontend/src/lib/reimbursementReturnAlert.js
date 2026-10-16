const MANAGER_REVIEW_STATUSES = ['accounting_reviewed', 'accounting_manager_review'];
const TREASURY_RESOLVED_STATUSES = ['accounting_manager_approved', 'treasury_review'];
const RETURNED_STATUS_BY_ROLE = {
    contabilidad: 'under_accounting_review',
    gerencia: 'accounting_manager_review',
    tesoreria: 'treasury_review',
};

export function obtenerAlertaDevolucionPersistida(solicitud, currentRole) {
    const role = String(currentRole || '').toLowerCase().trim();
    const backendStatus = String(
        solicitud?.backendStatus || solicitud?.backend_status || ''
    ).toLowerCase();
    const correctionReturnStatus = String(
        solicitud?.correctionReturnStatus || solicitud?.correction_return_status || ''
    ).toLowerCase();
    const returnedStatus = RETURNED_STATUS_BY_ROLE[role];

    return {
        tieneEstadoPersistido: Boolean(correctionReturnStatus),
        esDevuelto: Boolean(
            returnedStatus
            && backendStatus === returnedStatus
            && correctionReturnStatus === returnedStatus
        ),
        esResuelto: (
            role === 'gerencia'
            && correctionReturnStatus === 'under_accounting_review'
            && MANAGER_REVIEW_STATUSES.includes(backendStatus)
        ) || (
            role === 'tesoreria'
            && correctionReturnStatus === 'accounting_manager_review'
            && TREASURY_RESOLVED_STATUSES.includes(backendStatus)
        ),
    };
}

export function obtenerPrioridadBandeja(currentRole, alerta) {
    const role = String(currentRole || '').toLowerCase().trim();

    if (alerta.esDevuelto) return 1;
    if (alerta.esResuelto) return 2;

    if (role === 'contabilidad') {
        if (alerta.queueStatus === 'taken') return 3;
        if (alerta.queueStatus === 'taken_other') return 5;
        return 4;
    }

    if (['gerencia', 'tesoreria'].includes(role)) {
        return 3;
    }

    if (['tienda', 'direccion', 'admin'].includes(role)) {
        return 1;
    }

    if (alerta.queueStatus === 'taken') return 3;
    if (alerta.queueStatus === 'taken_other') return 4;
    return 2;
}
