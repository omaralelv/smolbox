import { newAuditId } from './captureAuditQueue.js';

export function createObservationSender(send, sessionKey) {
    const pending = new Map();
    let previousSession;
    return function submit(expenseId, note) {
        const session = sessionKey();
        if (session !== previousSession) {
            pending.clear();
            previousSession = session;
        }
        const key = expenseId;
        let entry = pending.get(key);
        if (!entry || entry.note !== note) {
            entry = { note, eventId: newAuditId(), sending: null };
            pending.set(key, entry);
        }
        if (!entry.sending) {
            entry.sending = Promise.resolve().then(() => send(expenseId, { note, eventId: entry.eventId }))
                .then((result) => {
                    if (pending.get(key) === entry) pending.delete(key);
                    return result;
                }).finally(() => { entry.sending = null; });
        }
        return entry.sending;
    };
}
