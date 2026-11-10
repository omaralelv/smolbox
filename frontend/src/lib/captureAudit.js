import { ensureHistoricalDraft, recordHistoricalEvent, recordExpenseCaptureEvent, startExpenseCapture } from './api';
import { createCaptureAuditQueue, newAuditId } from './captureAuditQueue';

const captures = new Map();

export function createCaptureAudit(requestId = null, historicalStoreId = null) {
    const id = newAuditId();
    let historicalRequestId;
    const queue = createCaptureAuditQueue({
        start: async () => {
            if (!historicalStoreId) return startExpenseCapture({ captureId: id, requestId });
            const draft = await ensureHistoricalDraft(historicalStoreId);
            historicalRequestId = draft.backendId;
        },
        send: (payload) => historicalStoreId
            ? recordHistoricalEvent(historicalRequestId, { ...payload, captureId: id })
            : recordExpenseCaptureEvent(id, payload),
    });
    const audit = {
        id,
        ...queue,
        activate: () => captures.set(id, audit),
        record: (action, details = {}) => {
            queue.record(action, details).catch((error) => {
                console.warn('No se pudo registrar el movimiento de captura.', error);
            });
        },
        finish: () => captures.delete(id),
    };
    return audit;
}

export function recordCaptureClick(captureId, label) {
    captures.get(captureId)?.record('click', { label });
}
