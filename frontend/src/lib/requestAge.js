const dateFormatter = new Intl.DateTimeFormat('es-MX', {
    timeZone: 'America/Mexico_City', year: 'numeric', month: '2-digit', day: '2-digit',
});
const terminalStatuses = new Set(['paid', 'closed', 'rejected']);

function timestamp(value) {
    return typeof value === 'string' && value.trim() ? Date.parse(value) : NaN;
}

function localDateKey(value) {
    return dateFormatter.format(value);
}

export function requestAgeDisplay(request) {
    const status = request?.backendStatus || request?.backend_status;
    const days = request?.elapsedDays ?? request?.elapsed_days;
    const start = timestamp(request?.firstSubmittedAt ?? request?.first_submitted_at);
    const stop = timestamp(request?.ageStoppedAt ?? request?.age_stopped_at);
    if (status === 'draft') return { label: 'Sin enviar', title: 'La solicitud no se ha enviado.' };
    if (!Number.isSafeInteger(days) || days < 0 || !Number.isFinite(start)
        || (terminalStatuses.has(status) && !Number.isFinite(stop))) {
        return { label: 'Sin fecha', title: 'No hay fechas suficientes para calcular la antig\u00fcedad.' };
    }
    const duration = `${days} ${days === 1 ? 'd\u00eda natural' : 'd\u00edas naturales'}`;
    return {
        label: String(days),
        title: `${duration} desde el primer env\u00edo: ${localDateKey(start)}.`
            + (Number.isFinite(stop) ? ` Contador detenido: ${localDateKey(stop)}.` : ''),
    };
}

export function shouldRefreshRequestAges(serverCalculatedAt, elapsedMilliseconds) {
    const serverTime = timestamp(serverCalculatedAt);
    if (!Number.isFinite(serverTime) || !Number.isFinite(elapsedMilliseconds)
        || elapsedMilliseconds < 0) return false;
    return localDateKey(serverTime) !== localDateKey(serverTime + elapsedMilliseconds);
}
