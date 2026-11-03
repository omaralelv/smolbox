import assert from 'node:assert/strict';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const storeId = '11111111-1111-4111-8111-111111111111';
const requestId = '22222222-2222-4222-8222-222222222222';
const expenseId = '33333333-3333-4333-8333-333333333333';
const root = '/api/v1/frontend/extemporaneos';
const file = Buffer.from('%PDF-1.4\n%%EOF');

async function scenario(role) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const errors = [];
    const calls = [];
    let paid = false;
    let expense = null;
    const events = [];
    const store = { id: storeId, code: 'T001', name: 'Centro', gerente: 'Gerente', cuentaBancaria: '123', estadoRegion: 'Centro' };
    const payload = () => ({
        id: paid ? 'E-T001-03112026-TEST' : 'E-BORRADOR', backendId: requestId,
        folio: paid ? 'E-T001-03112026-TEST' : 'Borrador extemporáneo', tienda: 'T001',
        fecha: '03/11/2026', backendStatus: paid ? 'historical_paid' : 'historical_draft',
        status: paid ? 'Pagada' : 'Borrador', esExtemporaneo: true,
        montoTotal: expense ? 20 : 0, calculatedTotal: expense ? 20 : 0, availableActions: [],
        gastos: expense ? [{ ...expense, canAddObservation: !paid }] : [],
    });
    await context.addInitScript((currentRole) => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', currentRole);
        localStorage.setItem('listaGastosSmolbox:11111111-1111-4111-8111-111111111111', '[{"id":"NORMAL-KEEP"}]');
    }, role);
    await context.route('**/api/v1/**', async (route) => {
        const req = route.request();
        const url = new URL(req.url());
        const path = url.pathname;
        calls.push(`${req.method()} ${path}`);
        let data = {};
        let status = 200;
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: role, stores: [], usuario: { id: 'user', nombre: role } };
        else if (path === `${root}/stores/me`) data = [store];
        else if (path === `${root}/stores/${storeId}/draft/me`) data = payload();
        else if (path === `${root}/${requestId}/me`) data = payload();
        else if (path === `${root}/${requestId}/events/me` && req.method() === 'GET') data = events;
        else if (path === `${root}/${requestId}/events/me`) { status = 201; data = { id: req.postDataJSON().eventId }; }
        else if (path.endsWith('/cfdi/ocr-preview')) data = {
            extracted_total: 20, extracted_date: '2026-01-15', suggested_cfdi_uuid: null,
            confidence: 99, checksum_sha256: 'test', verification_token: 'preview-token',
        };
        else if (path === `${root}/${requestId}/expenses/me`) {
            const body = req.postDataJSON();
            assert.equal(body.documentType, 'vale');
            assert.equal(body.fecha, '2026-01-15');
            expense = { id: expenseId, backendId: expenseId, captureId: body.clientId,
                nombre: 'Gasto - Pasajes y Taxis', tipo: body.categoria, type: body.categoria,
                fecha: body.fecha, monto: 20, folio: 'N/A', observaciones: body.observaciones,
                createdAt: '2026-11-03T18:00:00Z', requiresAuthorization: false, backendStatus: 'historical' };
            data = payload(); status = 201;
        } else if (path === `${root}/expenses/${expenseId}/attachments/me`) {
            expense.urlVale = `${root}/attachments/file/download/me`;
            expense.downloadUrl = expense.urlVale;
            data = { id: 'file', filename: 'vale.pdf' }; status = 201;
        } else if (path === `${root}/expenses/${expenseId}/observations/me`) {
            const body = req.postDataJSON();
            const event = { id: body.eventId, expense_id: expenseId, action: 'expense_observation_added',
                message: body.note, created_at: '2026-11-03T18:01:00Z', event_payload: { actor_role: 'accountant' } };
            events.push(event); data = event; status = 201;
        } else if (path === `${root}/${requestId}/register/me`) {
            assert.deepEqual(req.postDataJSON().expectedExpenseIds, [expenseId]);
            paid = true; data = payload();
        } else if (path === '/api/v1/frontend/historico/me') data = paid ? [payload()] : [];
        else if (path === `${root}/attachments/file/download/me`) {
            await route.fulfill({ status: 200, contentType: 'application/pdf', body: file }); return;
        } else { errors.push(`Unexpected API ${req.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.setDefaultTimeout(12_000);
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('dialog', (dialog) => dialog.accept());
    return { context, page, errors, calls };
}

async function normalDraftSmoke() {
    const context = await browser.newContext();
    const calls = [];
    const errors = [];
    let expenses = [];
    const payload = () => ({ id: 'T001-NORMAL', backendId: requestId, tienda: 'T001',
        status: 'Borrador', backendStatus: 'draft', gastos: expenses, montoTotal: expenses.length * 20 });
    const store = { id: storeId, code: 'T001', name: 'Centro' };
    await context.addInitScript(() => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', 'admin');
    });
    await context.route('**/api/v1/**', async (route) => {
        const request = route.request();
        const path = new URL(request.url()).pathname;
        calls.push(`${request.method()} ${path}`);
        let data = {};
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: 'admin', stores: [store], activeStore: store };
        else if (path.endsWith('/frontend/stores/active/me')) data = [store];
        else if (path.startsWith('/api/v1/frontend/capturas/')) data = { id: request.postDataJSON()?.captureId || 'capture' };
        else if (path.endsWith('/cfdi/ocr-preview')) data = { extracted_total: 20, extracted_date: '2026-01-15', verification_token: 'normal-token' };
        else if (path.endsWith('/borrador/me')) data = payload();
        else if (path.endsWith(`/solicitudes/${requestId}/gastos/me`)) {
            const body = request.postDataJSON();
            expenses = [{ ...body, id: expenseId, backendId: expenseId, nombre: 'Gasto - Papelería',
                tipo: 'Papelería', monto: 20, backendStatus: 'pending', canAddObservation: true }];
            data = payload();
        } else if (path.endsWith(`/expenses/${expenseId}/attachments`)) data = { id: 'normal-file' };
        else if (path.endsWith('/audit-events')) data = [];
        else { errors.push(`Unexpected normal API ${request.method()} ${path}`); }
        await route.fulfill({ status: request.method() === 'POST' ? 201 : 200, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.setDefaultTimeout(12_000);
    page.on('dialog', (dialog) => dialog.accept());
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${baseURL}/gasto/nuevo`);
    await page.getByPlaceholder('DD/MM/AAAA').fill('15/01/2026');
    await page.getByPlaceholder('Ej. 123.45').fill('20');
    await page.getByRole('radio', { name: 'Cargar Vale', exact: true }).check();
    await page.locator('input[type="file"]').nth(1).setInputFiles({ name: 'vale.pdf', mimeType: 'application/pdf', buffer: file });
    await page.getByRole('button', { name: 'Validar Gasto', exact: true }).click();
    await page.getByText('Los datos ingresados coinciden.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Añadir', exact: true }).click();
    await page.waitForURL(`${baseURL}/solicitud/nueva`);
    await page.getByText('Gasto - Papelería', { exact: true }).waitFor();
    assert.ok(!calls.some((call) => call.includes('/extemporaneos')));
    assert.ok(calls.some((call) => call.includes(`/solicitudes/${requestId}/gastos/me`)));
    assert.deepEqual(errors, []);
    await context.close();
}

try {
    for (const role of ['contabilidad', 'admin']) {
        const test = await scenario(role);
        const { page } = test;
        await page.goto(`${baseURL}/historico`);
        await page.getByRole('button', { name: '+ Solicitud Extemporánea', exact: true }).click();
        await page.getByRole('button', { name: 'Añadir Gasto', exact: true }).waitFor();
        await page.getByRole('button', { name: 'Añadir Gasto', exact: true }).click();
        await page.waitForURL(`${baseURL}/gasto/extemporaneo`);
        await page.getByPlaceholder('DD/MM/AAAA').fill('15/01/2026');
        await page.getByPlaceholder('Ej. 123.45').fill('20');
        await page.locator('select').first().selectOption({ label: 'Pasajes y Taxis' });
        await page.getByRole('radio', { name: 'Cargar Vale', exact: true }).check();
        await page.locator('input[type="file"]').nth(1).setInputFiles({ name: 'vale.pdf', mimeType: 'application/pdf', buffer: file });
        await page.locator('textarea').fill('Nota antes de registrar');
        await page.getByRole('button', { name: 'Validar Gasto', exact: true }).click();
        await page.getByText('Los datos ingresados coinciden.', { exact: true }).waitFor();
        await page.getByRole('button', { name: 'Añadir', exact: true }).click();
        await page.waitForURL(`${baseURL}/solicitud/extemporanea`);
        await page.getByText('Gasto - Pasajes y Taxis', { exact: true }).waitFor();
        await page.reload();
        await page.getByText('Gasto - Pasajes y Taxis', { exact: true }).waitFor();
        await page.getByTitle('Observaciones', { exact: true }).click();
        const text = page.locator('textarea');
        await text.fill('Comentario persistente');
        await page.getByRole('button', { name: /Enviar/ }).last().click();
        await page.getByText('Comentario persistente', { exact: true }).waitFor();
        await page.getByRole('button', { name: '✕', exact: true }).click();
        await page.getByRole('button', { name: 'Enviar Solicitud', exact: true }).click();
        await page.waitForURL(`${baseURL}/historico`);
        await page.getByText('Extemporáneo', { exact: true }).waitFor();
        assert.equal(await page.locator('[data-request-age]').textContent(), '-');
        await page.getByRole('button', { name: 'Abrir', exact: true }).click();
        await page.waitForURL(`${baseURL}/historico/extemporanea/${requestId}`);
        await page.getByText('Gasto - Pasajes y Taxis', { exact: true }).waitFor();
        assert.equal(await page.getByRole('button', { name: 'Enviar Solicitud', exact: true }).count(), 0);
        assert.equal(await page.getByTitle('Eliminar gasto', { exact: true }).count(), 0);
        await page.reload();
        await page.getByText('Gasto - Pasajes y Taxis', { exact: true }).waitFor();
        await page.screenshot({ path: `/tmp/smolbox-extemporaneo-${role}.png`, fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: `/tmp/smolbox-extemporaneo-${role}-mobile.png`, fullPage: true });
        assert.ok(!test.calls.some((call) => /reimbursement-requests|\/solicitudes\/|\/capturas/.test(call)), 'no operational API or period access');
        assert.equal(await page.evaluate(() => localStorage.getItem('listaGastosSmolbox:11111111-1111-4111-8111-111111111111')), '[{"id":"NORMAL-KEEP"}]');
        assert.deepEqual(test.errors, []);
        await test.context.close();
    }
    await normalDraftSmoke();
    process.stdout.write('Historical browser checks passed: admin/accounting, stores, OCR, saved expense, draft reload, observations, paid history, read-only archive, independent normal draft, normal expense creation and desktop/mobile.\n');
} catch (error) {
    for (const context of browser.contexts()) {
        for (const page of context.pages()) {
            await page.screenshot({ path: '/tmp/smolbox-extemporaneo-failure.png', fullPage: true }).catch(() => {});
            process.stderr.write(`${page.url()}\n${(await page.locator('body').innerText()).slice(0, 5000)}\n`);
        }
    }
    throw error;
} finally { await browser.close(); }
