export function newAuditId() {
    if (globalThis.crypto.randomUUID) return globalThis.crypto.randomUUID();
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function createCaptureAuditQueue({ start, send, wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)) }) {
    const pending = [];
    let started = false;
    let sending = null;

    async function retry(operation) {
        for (let attempt = 0; ; attempt += 1) {
            try {
                return await operation();
            } catch (error) {
                if (attempt === 2 || (error.status && error.status < 500 && error.status !== 429)) throw error;
                await wait(300 * (attempt + 1));
            }
        }
    }

    async function drain() {
        if (!started) {
            await retry(start);
            started = true;
        }
        while (pending.length) {
            await retry(() => send(pending[0]));
            pending.shift();
        }
    }

    async function flush() {
        do {
            if (!sending) sending = drain().finally(() => { sending = null; });
            await sending;
        } while (pending.length);
    }

    function record(action, details = {}) {
        pending.push({ ...details, action, eventId: newAuditId() });
        return flush();
    }

    return { record, flush };
}
