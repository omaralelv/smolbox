const MANAGER_REVIEW_STATUSES = ['accounting_reviewed', 'accounting_manager_review'];
const TREASURY_RESOLVED_STATUSES = ['accounting_manager_approved', 'treasury_review'];

export function obtenerAlertaDevolucionPersistida(solicitud, currentRole) {
    const role = String(currentRole || '').toLowerCase().trim();
    const backendStatus = String(
        solicitud?.backendStatus || solicitud?.backend_status || ''
    ).toLowerCase();
    const correctionReturnStatus = String(
        solicitud?.correctionReturnStatus || solicitud?.correction_return_status || ''
    ).toLowerCase();

    return {
        tieneEstadoPersistido: Boolean(correctionReturnStatus),
        esDevuelto: role === 'gerencia'
            && backendStatus === 'accounting_manager_review'
            && correctionReturnStatus === 'accounting_manager_review',
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
