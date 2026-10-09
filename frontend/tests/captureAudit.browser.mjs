import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5181';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
const events = [];
const creations = [];
const captures = new Map();
const failures = [];
let failOcr = false;
const storeId = randomUUID();
const actorId = randomUUID();
const unreadable = 'No se pudo leer el documento con OCR.\nEl archivo cargado no tiene un formato compatible o no puede ser procesado.\nPor favor, carga nuevamente el archivo en formato PDF válido.';

function event(id, action, payload, message, requestId = null, expenseId = null) {
    return { id, action, message, event_payload: { ...payload, store_id: storeId, store_code: 'T001', actor_role: 'store', actor_name: 'Usuario Captura' },
        actor_user_id: actorId, actor_type: 'user', actor_name: 'Usuario Captura', actor_role: 'store',
        created_at: new Date().toISOString(), reimbursement_request_id: requestId, expense_id: expenseId,
        store_code: 'T001', request_folio: requestId ? 'T001-PRUEBA' : null };
}

await context.addInitScript(() => {
    localStorage.setItem('smolboxApiToken', 'test-token');
    localStorage.setItem('smolboxFrontendRole', 'tienda');
});
await context.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let data = {};
    let status = 200;
    if (path.endsWith('/health')) data = { version: 'test' };
    else if (path.endsWith('/frontend/context/me')) data = { currentRole: 'tienda', tienda: 'T001', gerente: 'Usuario Captura', usuario: { id: actorId } };
    else if (path.endsWith('/frontend/capturas/me')) {
        const body = request.postDataJSON();
        if (!captures.has(body.captureId)) {
            const anchor = event(body.captureId, 'expense_capture_started', { capture_id: body.captureId }, 'Captura de gasto iniciada.');
            captures.set(body.captureId, anchor);
            events.push(anchor);
        }
        data = captures.get(body.captureId);
        status = 201;
    } else if (/\/capturas\/[^/]+\/eventos\/me$/.test(path)) {
        const body = request.postDataJSON();
        const id = path.split('/').at(-3);
        const message = body.action === 'field_changed'
            ? `Cambio de ${body.field} de ${body.previousValue} a ${body.value} durante captura.`
            : body.action === 'cancelled' ? 'Captura cancelada sin añadir el gasto.' : body.message || body.label || body.filename || body.action;
        data = event(body.eventId, `expense_capture_${body.action}`, { ...body, capture_id: id }, message);
        if (!events.some((item) => item.id === body.eventId)) events.push(data);
        status = 201;
    } else if (path.endsWith('/cfdi/ocr-preview')) {
        const body = request.postData();
        const captureId = [...captures.keys()].find((id) => body.includes(id));
        assert.ok(captureId, 'OCR must carry the capture identifier');
        events.push(event(randomUUID(), 'expense_capture_ocr_started', { capture_id: captureId }, 'Lectura OCR iniciada.'));
        if (failOcr) {
            status = 502;
            data = { detail: { code: 'OCR_UNREADABLE_DOCUMENT', message: unreadable } };
            events.push(event(randomUUID(), 'expense_capture_ocr_failed', { capture_id: captureId }, 'Lectura OCR no completada.'));
        } else {
            data = { extracted_total: '100.00', extracted_date: '2026-08-07', suggested_cfdi_uuid: null, checksum_sha256: 'test', verification_token: 'v1.test' };
            events.push(event(randomUUID(), 'expense_capture_ocr_completed', { capture_id: captureId }, 'Documento leído y validado con OCR antes de añadir el gasto.'));
        }
    } else if (path.endsWith('/frontend/solicitudes/me') && request.method() === 'POST') {
        const body = request.postDataJSON();
        const expense = body.gastos[0];
        assert.ok(captures.has(expense.captureId));
        creations.push(body);
        const requestId = randomUUID();
        const expenseId = randomUUID();
        for (const item of events.filter((row) => row.event_payload.capture_id === expense.captureId)) {
            item.reimbursement_request_id = requestId;
            item.expense_id = expenseId;
            item.request_folio = 'T001-PRUEBA';
        }
        data = { id: 'T001-PRUEBA', backendId: requestId, folio: 'T001-PRUEBA', tienda: 'T001', status: 'Borrador',
            gastos: [{ id: expenseId, backendId: expenseId, tipo: expense.categoria, monto: Number(expense.monto), facturas: 1, folio: 'N/A' }] };
        status = 201;
    } else if (/\/expenses\/[^/]+\/attachments$/.test(path)) { data = { id: randomUUID() }; status = 201; }
    else if (path.endsWith('/frontend/audit-events/me')) data = events.slice(Number(url.searchParams.get('offset') || 0), 200);
    else if (path.endsWith('/frontend/bandeja/me') || path.endsWith('/frontend/historico/me')) data = [];
    else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
});

const page = await context.newPage();
const dialogs = [];
page.on('pageerror', (error) => failures.push(error.message));
page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });

async function fillCapture() {
    await page.goto(`${baseURL}/gasto/nuevo`);
    await page.getByRole('heading', { name: 'Añadir Gasto', exact: true }).waitFor();
    await page.locator('select').first().selectOption('Agua');
    await page.getByPlaceholder('DD/MM/AAAA').fill('07/08/2026');
    await page.getByPlaceholder('Ej. 123.45').fill('100');
    await page.getByRole('radio', { name: 'Cargar Vale' }).check();
    await page.locator('input[type=file]').nth(1).setInputFiles({ name: 'vale.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\ncontent\n%%EOF') });
    await page.getByRole('button', { name: 'Validar Gasto', exact: true }).click();
    await page.waitForFunction(() => !document.body.innerText.includes('Procesando documentos'));
    await page.waitForTimeout(200);
}

try {
    await fillCapture();
    assert.equal(creations.length, 0, 'validation must not create an expense or request');
    assert.ok(events.some((row) => row.action === 'expense_capture_validation_completed'));
    assert.ok(events.some((row) => row.event_payload.field === 'category' && row.event_payload.value === 'Agua'));
    assert.ok(events.some((row) => row.event_payload.filename === 'vale.pdf'));
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
    await page.waitForURL('**/solicitud/nueva');
    assert.ok(events.some((row) => row.action === 'expense_capture_cancelled'));
    await page.goto(`${baseURL}/bitacora`);
    await page.getByText('Captura no añadida', { exact: true }).first().waitFor();
    await page.getByText('Captura cancelada sin añadir el gasto.', { exact: true }).waitFor();
    assert.ok(await page.getByText('Usuario Captura', { exact: true }).count());
    assert.equal(await page.getByText('Solicitudes', { exact: true }).locator('..').locator('strong').innerText(), '0');
    await page.clock.install();
    events.push(event(randomUUID(), 'expense_capture_click', { capture_id: events[0].id }, 'Movimiento recibido sin recargar.'));
    await page.clock.runFor(10_050);
    await page.getByText('Movimiento recibido sin recargar.', { exact: true }).waitFor();
    await page.screenshot({ path: '/tmp/smolbox-capture-audit-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    const content = page.locator('main').last();
    assert.ok((await content.boundingBox()).width <= 390, 'audit content must fit the mobile viewport');
    await page.screenshot({ path: '/tmp/smolbox-capture-audit-mobile.png', fullPage: true });
    await page.setViewportSize({ width: 1366, height: 900 });

    failOcr = true;
    await fillCapture();
    assert.equal(dialogs.at(-1), unreadable, 'existing OCR alert must remain unchanged');
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
    await page.waitForURL('**/solicitud/nueva');

    failOcr = false;
    await fillCapture();
    await page.getByRole('button', { name: 'Añadir', exact: true }).click();
    await page.waitForURL('**/solicitud/nueva');
    assert.equal(creations.length, 1);
    assert.ok(events.some((row) => row.reimbursement_request_id && row.expense_id));
    assert.equal(dialogs.at(-1), '¡Gasto guardado exitosamente en la solicitud!');
    assert.deepEqual(failures, []);
    console.log('Browser checks passed: capture without adding, cancellation, OCR failure alert, save and audit linkage; desktop/mobile screenshots captured.');
} finally {
    await browser.close();
}
