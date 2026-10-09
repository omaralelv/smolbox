import { recordExpenseCaptureEvent, startExpenseCapture } from './api';
import { createCaptureAuditQueue, newAuditId } from './captureAuditQueue';

const captures = new Map();

export function createCaptureAudit(requestId = null) {
    const id = newAuditId();
    const queue = createCaptureAuditQueue({
        start: () => startExpenseCapture({ captureId: id, requestId }),
        send: (payload) => recordExpenseCaptureEvent(id, payload),
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
