import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const initialText = 'INITIAL STORE NOTE';
const warning = 'No se pudieron actualizar las observaciones. Se conserva el historial cargado.';

async function openHistory(role, { storeDraft = false, failInitially = false, persistedInitial = false } = {}) {
    const requestId = randomUUID();
    const expenseId = randomUUID();
    const authorizer = role === 'supervisor';
    const expense = {
        id: expenseId, backendId: expenseId, nombre: 'Gasto - Agua', tipo: 'Agua', monto: 100,
        fecha: '2026-08-07', observaciones: initialText, requiresAuthorization: true,
        backendStatus: 'submitted', folio: 'N/A', facturas: 1,
    };
    const requestData = {
        backendId: requestId, folio: 'T001-TEST', id: 'T001-TEST', tienda: 'T001',
        backendStatus: storeDraft ? 'draft' : authorizer ? 'authorization_review' : 'under_accounting_review',
        availableActions: [], gastos: [expense],
    };
    const events = Array.from({ length: 225 }, (_, index) => ({
        id: `event-${String(index).padStart(3, '0')}`, expense_id: expenseId,
        message: `SUPERVISOR NOTE ${String(index).padStart(3, '0')}`,
        action: 'expense_observation_added', created_at: new Date(Date.UTC(2026, 7, 8, 10, 0, index)).toISOString(),
        event_payload: { actor_role: 'authorizer' },
    })).reverse();
    if (persistedInitial) events.push({
        id: 'initial-event', expense_id: expenseId, message: initialText,
        action: 'expense_observation_added', created_at: '2026-08-07T10:00:00Z',
        event_payload: { actor_role: 'store', is_initial_observation: true },
    });
    const reads = [];
    const posts = [];
    const failures = [];
    const dialogs = [];
    let failingOffset = failInitially ? 0 : null;
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.addInitScript(({ role, expense, requestData, storeDraft, authorizer }) => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', role);
        if (storeDraft) {
            localStorage.setItem('listaGastosSmolbox', JSON.stringify([expense]));
            localStorage.setItem('solicitudBorradorBackendSmolbox', JSON.stringify({ backendId: requestData.backendId }));
        } else if (!authorizer) {
            history.replaceState({ usr: { categoria: 'Agua', solicitudFolio: requestData.folio,
                solicitudBackendId: requestData.backendId, desglose: [expense] }, key: 'history', idx: 0 }, '', location.href);
        }
    }, { role, expense, requestData, storeDraft, authorizer });
    await context.route('**/api/v1/**', async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const path = url.pathname;
        let data = {};
        let status = 200;
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: role, tienda: 'T001' };
        else if (path.endsWith('/frontend/bandeja/me')) data = [requestData];
        else if (path.endsWith('/frontend/historico/me')) data = [];
        else if (path.endsWith(`/solicitudes/${requestId}/me`)) data = requestData;
        else if (path.endsWith('/audit-events')) {
            assert.equal(url.searchParams.get('observations_only'), 'true');
            assert.equal(url.searchParams.get('limit'), '200');
            const offset = Number(url.searchParams.get('offset'));
            reads.push(offset);
            if (offset === failingOffset) { status = 503; data = { detail: 'Test read failure' }; }
            else data = events.slice(offset, offset + 200);
        } else if (path.endsWith('/clicks/me')) status = 201;
        else if (path.endsWith('/observation/me')) {
            posts.push(request.postDataJSON());
            events.unshift({
                id: randomUUID(), expense_id: expenseId, message: posts.at(-1).note,
                action: 'expense_observation_added', created_at: '2026-08-09T10:00:00Z',
                event_payload: { actor_role: 'accountant' },
            });
            data = { id: expenseId, review_note: posts.at(-1).note };
        } else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));
    page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
    await page.goto(`${baseURL}${storeDraft ? '/solicitud/nueva' : authorizer ? '/autorizacion' : '/detalle'}`);
    await page.getByRole('button', { name: 'Observaciones', exact: true }).first().click();
    await page.getByPlaceholder('Nueva observaci\u00f3n...').waitFor();
    return { context, page, reads, posts, failures, dialogs, failAt: (offset) => { failingOffset = offset; } };
}

async function expectCompleteHistory(form) {
    await form.page.getByText('SUPERVISOR NOTE 000', { exact: true }).waitFor();
    await form.page.getByText('SUPERVISOR NOTE 224', { exact: true }).waitFor();
    assert.equal(await form.page.getByText(/^SUPERVISOR NOTE \d{3}$/).count(), 225);
    assert.equal(await form.page.getByText(initialText, { exact: true }).count(), 1);
    assert.ok(form.reads.includes(200), 'automatically requests the second page');
    assert.deepEqual(form.failures, []);
}

try {
    for (const role of ['tienda', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin', 'supervisor']) {
        const form = await openHistory(role, { persistedInitial: role === 'admin' });
        await expectCompleteHistory(form);
        await form.context.close();
    }
    const draft = await openHistory('tienda', { storeDraft: true });
    await expectCompleteHistory(draft);
    await draft.context.close();

    const initialFailure = await openHistory('supervisor', { failInitially: true });
    await initialFailure.page.getByRole('alert').getByText(warning, { exact: true }).waitFor();
    await initialFailure.page.getByText(initialText, { exact: true }).waitFor();
    initialFailure.failAt(null);
    await initialFailure.page.getByRole('button', { name: 'Reintentar', exact: true }).click();
    await expectCompleteHistory(initialFailure);
    assert.equal(await initialFailure.page.getByRole('alert').count(), 0);
    await initialFailure.context.close();

    const recovery = await openHistory('contabilidad');
    await expectCompleteHistory(recovery);
    recovery.failAt(200);
    await recovery.page.getByPlaceholder('Nueva observaci\u00f3n...').fill('NEW SAVED NOTE');
    await recovery.page.locator('form').getByRole('button').click();
    await recovery.page.getByRole('alert').getByText(warning, { exact: true }).waitFor();
    await expectCompleteHistory(recovery);
    assert.equal(recovery.posts.length, 1, 'read failure does not resubmit the saved observation');
    assert.deepEqual(recovery.dialogs, [], 'successful save is not reported as a failed write');
    await recovery.page.screenshot({ path: '/tmp/smolbox-observation-history-retry.png', fullPage: true });
    await recovery.page.setViewportSize({ width: 390, height: 844 });
    const retryFits = await recovery.page.getByRole('alert').evaluate((alert) => {
        const panel = alert.getBoundingClientRect();
        const button = alert.querySelector('button').getBoundingClientRect();
        return alert.scrollWidth <= alert.clientWidth && button.left >= panel.left && button.right <= panel.right;
    });
    assert.equal(retryFits, true, 'retry message and button fit the mobile panel');
    await recovery.page.screenshot({ path: '/tmp/smolbox-observation-history-mobile.png', fullPage: true });
    await recovery.page.setViewportSize({ width: 1440, height: 1000 });
    recovery.failAt(null);
    await recovery.page.getByRole('button', { name: 'Reintentar', exact: true }).click();
    await recovery.page.getByText('NEW SAVED NOTE', { exact: true }).waitFor();
    await expectCompleteHistory(recovery);
    assert.equal(await recovery.page.getByRole('alert').count(), 0);
    assert.equal(recovery.posts.length, 1);
    await recovery.page.screenshot({ path: '/tmp/smolbox-observation-history-complete.png', fullPage: true });
    await recovery.context.close();
    console.log('Browser checks passed: 225 observations, initial note and all seven roles; saved store draft; first/second-page failures and retry without data loss.');
} finally {
    await browser.close();
}
