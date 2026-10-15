import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const initialText = 'INITIAL STORE NOTE';
const warning = 'No se pudieron actualizar las observaciones. Se conserva el historial cargado.';
const savedWarning = 'La observaci\u00f3n se guard\u00f3, pero no se pudo actualizar el historial. Reintenta la consulta; no es necesario enviarla otra vez.';

async function openHistory(role, { storeDraft = false, failInitially = false, persistedInitial = false,
    partition = false, canComment, requestStatus, pauseSave = false, failSave = false } = {}) {
    const requestId = randomUUID();
    const expenseId = randomUUID();
    const authorizer = role === 'supervisor';
    const parentId = partition ? randomUUID() : null;
    const backendRole = { tienda: 'store', supervisor: 'authorizer', contabilidad: 'accountant', gerencia: 'accounting_manager',
        tesoreria: 'treasury', direccion: 'director', admin: 'admin' }[role];
    const writable = canComment ?? (storeDraft || ['supervisor', 'contabilidad', 'admin'].includes(role));
    const description = partition ? 'Partici\u00f3n 1/2 del gasto Gasto - Agua.' : initialText;
    const expense = {
        id: expenseId, backendId: expenseId, nombre: partition ? 'Partici\u00f3n 1 / 2 - Agua' : 'Gasto - Agua', tipo: 'Agua', monto: 100,
        fecha: '2026-08-07', observaciones: description, requiresAuthorization: true,
        backendStatus: 'submitted', folio: 'N/A', facturas: 1,
        canAddObservation: writable, createdAt: '2026-10-15T18:13:00Z',
        esHijoParticion: partition, idOriginal: parentId,
    };
    const requestData = {
        backendId: requestId, folio: 'T001-TEST', id: 'T001-TEST', tienda: 'T001',
        backendStatus: requestStatus || (storeDraft ? 'draft' : authorizer ? 'authorization_review' : 'under_accounting_review'),
        availableActions: [], gastos: [expense],
    };
    const events = Array.from({ length: 225 }, (_, index) => ({
        id: `event-${String(index).padStart(3, '0')}`, expense_id: expenseId,
        message: `SUPERVISOR NOTE ${String(index).padStart(3, '0')}`,
        action: 'expense_observation_added', created_at: new Date(Date.UTC(2026, 7, 8, 10, 0, index)).toISOString(),
        event_payload: { actor_role: 'authorizer' },
    })).reverse();
    if (partition) events.push({
        id: 'parent-note', expense_id: parentId, message: initialText,
        action: 'expense_observation_added', created_at: '2026-10-15T17:13:00Z', event_payload: { actor_role: 'store' },
    });
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
    let releaseSave;
    const saveGate = new Promise((resolve) => { releaseSave = resolve; });
    let markSaveStarted;
    const saveStarted = new Promise((resolve) => { markSaveStarted = resolve; });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'es-MX', timezoneId: 'America/Mexico_City' });
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
            markSaveStarted();
            if (pauseSave) await saveGate;
            if (failSave) {
                status = 409;
                data = { detail: { code: 'ROLE_NOT_ALLOWED', message: 'Role cannot perform this expense action.' } };
            } else {
                events.unshift({
                id: randomUUID(), expense_id: expenseId, message: posts.at(-1).note,
                action: 'expense_observation_added', created_at: '2026-10-15T18:14:00Z',
                event_payload: { actor_role: backendRole },
                });
                data = { id: expenseId, review_note: posts.at(-1).note };
            }
        } else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));
    page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
    await page.goto(`${baseURL}${storeDraft ? '/solicitud/nueva' : authorizer ? '/autorizacion' : '/detalle'}`);
    await page.getByRole('button', { name: 'Observaciones', exact: true }).first().click();
    await page.getByText(description, { exact: true }).waitFor();
    return { context, page, reads, posts, failures, dialogs, saveStarted, releaseSave, writable, failAt: (offset) => { failingOffset = offset; } };
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
        assert.equal(await form.page.getByPlaceholder('Nueva observaci\u00f3n...').count(), form.writable ? 1 : 0, role);
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
    await recovery.page.getByRole('alert').getByText(savedWarning, { exact: true }).waitFor();
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

    for (const [role, options] of [['tienda', { storeDraft: true }], ['contabilidad', {}], ['supervisor', {}]]) {
        const form = await openHistory(role, { ...options, pauseSave: true });
        await expectCompleteHistory(form);
        const editor = form.page.getByPlaceholder('Nueva observaci\u00f3n...');
        await editor.fill('COMMENT SAVED ONCE');
        await form.page.getByRole('button', { name: 'Enviar observaci\u00f3n', exact: true }).evaluate((button) => { button.click(); button.click(); });
        await form.saveStarted;
        assert.equal(form.posts.length, 1, `${role} double click sends only one write`);
        assert.equal(await editor.isDisabled(), true);
        form.releaseSave();
        await form.page.getByText('COMMENT SAVED ONCE', { exact: true }).waitFor();
        assert.equal(form.posts.length, 1);
        assert.equal(await form.page.getByText('COMMENT SAVED ONCE', { exact: true }).count(), 1);
        assert.deepEqual(form.dialogs, []);
        assert.deepEqual(form.failures, []);
        await form.context.close();
    }

    const rejected = await openHistory('tienda', { storeDraft: true, failSave: true });
    const rejectedEditor = rejected.page.getByPlaceholder('Nueva observaci\u00f3n...');
    await rejectedEditor.fill('REJECTED COMMENT');
    const errorDialog = rejected.page.waitForEvent('dialog');
    await rejected.page.getByRole('button', { name: 'Enviar observaci\u00f3n', exact: true }).click();
    assert.ok((await errorDialog).message().includes('no tiene permisos'));
    assert.equal(await rejectedEditor.inputValue(), 'REJECTED COMMENT', 'a failed write preserves the text');
    assert.equal(await rejected.page.locator('div').filter({ hasText: /^REJECTED COMMENT$/ }).count(), 0);
    assert.equal(rejected.posts.length, 1);
    assert.equal(await rejected.page.getByRole('alert').count(), 0, 'no false save acknowledgement');
    await rejected.context.close();

    const partition = await openHistory('tesoreria', { partition: true, canComment: true, requestStatus: 'treasury_review' });
    await expectCompleteHistory(partition);
    const systemRecord = partition.page.getByText('Partici\u00f3n 1/2 del gasto Gasto - Agua.', { exact: true }).locator('..');
    assert.ok((await systemRecord.innerText()).includes('SISTEMA'));
    assert.ok((await systemRecord.innerText()).includes('15/10/2026'));
    assert.ok((await systemRecord.innerText()).includes('Registro autom\u00e1tico'));
    assert.ok(!(await systemRecord.innerText()).includes('TIENDA'));
    assert.ok((await partition.page.getByText(initialText, { exact: true }).locator('..').innerText()).includes('Gasto original'));
    assert.ok((await partition.page.getByText('SUPERVISOR NOTE 000', { exact: true }).locator('..').innerText()).includes('Esta partici\u00f3n'));
    await systemRecord.scrollIntoViewIfNeeded();
    await partition.page.screenshot({ path: '/tmp/smolbox-partition-observation-origins.png', fullPage: true });
    await partition.context.close();

    const paid = await openHistory('tesoreria', { canComment: false, requestStatus: 'paid' });
    await expectCompleteHistory(paid);
    assert.equal(await paid.page.getByPlaceholder('Nueva observaci\u00f3n...').count(), 0, 'paid history remains readable without a send form');
    await paid.context.close();
    console.log('Browser checks passed: complete history, seven roles, store draft permissions, readonly states, partition origins and dates, single-flight writes, failed writes and saved-but-refresh-failed recovery.');
} finally {
    await browser.close();
}
