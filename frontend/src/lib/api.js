const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '');
const TOKEN_KEY = 'smolboxApiToken';
const ROLE_KEY = 'smolboxFrontendRole';

const ACTION_TARGET_STATUS = {
    submit_request: 'submitted',
    start_authorization_review: 'authorization_review',
    approve_authorization: 'authorized',
    start_accounting_review: 'under_accounting_review',
    mark_accounting_reviewed: 'accounting_reviewed',
    start_accounting_manager_review: 'accounting_manager_review',
    approve_accounting_manager: 'accounting_manager_approved',
    start_treasury_review: 'treasury_review',
    send_to_direction: 'direction_review',
    approve_direction: 'direction_approved',
    mark_approved_for_payment: 'approved_for_payment',
    close_request: 'closed',
    reject_request: 'rejected',
    return_to_accounting: 'under_accounting_review',
    return_to_manager: 'accounting_manager_review',
    return_to_treasury: 'treasury_review',
};

export function currentToken() {
    return localStorage.getItem(TOKEN_KEY);
}

export function currentStoredRole() {
    return localStorage.getItem(ROLE_KEY) || 'admin';
}

export function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
}

export async function login(email, password) {
    const body = await request('/auth/login', {
        method: 'POST',
        skipAuth: true,
        body: { email, password },
    });
    localStorage.setItem(TOKEN_KEY, body.access_token);
    const context = await getFrontendContext();
    localStorage.setItem(ROLE_KEY, context.currentRole);
    return { token: body.access_token, context };
}

export async function getFrontendContext() {
    return request('/frontend/context/me');
}

export async function getFrontendBandeja() {
    return request('/frontend/bandeja/me');
}

export async function getFrontendSolicitud(requestIdOrFolio) {
    return request(`/frontend/solicitudes/${encodeURIComponent(requestIdOrFolio)}/me`);
}

export async function createFrontendSolicitud(payload) {
    return request('/frontend/solicitudes/me', {
        method: 'POST',
        body: payload,
    });
}

export async function addFrontendGasto(requestIdOrFolio, payload) {
    return request(`/frontend/solicitudes/${encodeURIComponent(requestIdOrFolio)}/gastos/me`, {
        method: 'POST',
        body: payload,
    });
}

export async function runAutomatedReview(requestId) {
    return request(`/reimbursement-requests/${requestId}/automated-review`, {
        method: 'POST',
    });
}

export async function executeRequestAction(requestId, action) {
    if (action === 'prepare_sap_policy') {
        return request(`/reimbursement-requests/${requestId}/sap-policy/prepare/me`, {
            method: 'POST',
            body: {
                reference: `SAP-${Date.now()}`,
                note: 'Póliza preparada desde frontend.',
            },
        });
    }

    if (action === 'record_payment') {
        return request(`/reimbursement-requests/${requestId}/payments/me`, {
            method: 'POST',
            body: {
                reference: `PAGO-${Date.now()}`,
                payment_method: 'transfer',
                note: 'Pago confirmado desde frontend.',
            },
        });
    }

    const targetStatus = ACTION_TARGET_STATUS[action];
    if (!targetStatus) {
        throw new Error(`Acción no conectada: ${action}`);
    }

    return request(`/reimbursement-requests/${requestId}/transition/me`, {
        method: 'POST',
        body: {
            target_status: targetStatus,
            note: `Acción ejecutada desde frontend: ${action}`,
        },
    });
}

export async function uploadExpenseAttachment(expenseId, file, attachmentType = 'receipt') {
    const formData = new FormData();
    formData.append('attachment_type', attachmentType);
    formData.append('file', file);
    return request(`/expenses/${expenseId}/attachments`, {
        method: 'POST',
        body: formData,
    });
}

export async function parseCfdi(file) {
    const formData = new FormData();
    formData.append('file', file);
    return request('/cfdi/parse', {
        method: 'POST',
        body: formData,
    });
}

export async function checkCfdiUuidAvailability(uuid) {
    return request(`/cfdi/uuid/${encodeURIComponent(uuid)}/availability`);
}

export async function validateExpenseCfdi(expenseId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/expenses/${expenseId}/cfdi/validate`, {
        method: 'POST',
        body: formData,
    });
}

export async function removeExpense(expenseId, reason) {
    return request(`/expenses/${expenseId}/remove/me`, {
        method: 'POST',
        body: {
            reason,
            adjust_reported_total: true,
        },
    });
}

export async function updateExpenseForReview(expenseId, payload) {
    return request(`/expenses/${expenseId}/review/me`, {
        method: 'PATCH',
        body: payload,
    });
}

export function apiErrorMessage(error) {
    if (!error) return 'No se pudo completar la operación.';
    return error.message || 'No se pudo completar la operación.';
}

export function apiFileUrl(path) {
    if (!path) return null;
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    const cleanPath = path.startsWith('/api/v1') ? path.slice('/api/v1'.length) : path;
    return `${API_BASE_URL}${cleanPath}`;
}

export async function openProtectedFile(path) {
    const url = apiFileUrl(path);
    const token = currentToken();
    if (!url || !token) {
        throw new Error('No hay sesión activa para abrir el archivo.');
    }

    const response = await fetch(url, {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });

    if (!response.ok) {
        const detail = await readError(response);
        throw new Error(detail);
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    window.open(objectUrl, '_blank');
}

export async function request(path, options = {}) {
    const headers = {};
    const isFormData = options.body instanceof FormData;

    if (!isFormData) {
        headers['Content-Type'] = 'application/json';
    }

    if (!options.skipAuth) {
        const token = currentToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
        method: options.method || 'GET',
        headers,
        body: isFormData ? options.body : options.body ? JSON.stringify(options.body) : undefined,
    });

    if (!response.ok) {
        const detail = await readError(response);
        throw new Error(detail);
    }

    if (response.status === 204) {
        return null;
    }
    return response.json();
}

async function readError(response) {
    try {
        const data = await response.json();
        if (typeof data.detail === 'string') return data.detail;
        if (data.detail?.message) return data.detail.message;
        if (data.message) return data.message;
        return JSON.stringify(data.detail || data);
    } catch {
        return `Error ${response.status}`;
    }
}
