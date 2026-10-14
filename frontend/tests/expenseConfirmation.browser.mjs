import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const fiscalUuid = '99999999-9999-4999-8999-999999999999';
const successMessage = '\u00a1Gasto guardado exitosamente en la solicitud!';
const confirmName = 'Confirmar y A\u00f1adir';
const addName = 'A\u00f1adir';

async function openForm({ documentType = 'factura', xml = false, existing = false, pauseSave = false, failOnce = false } = {}) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const requestId = randomUUID();
    const expenseId = randomUUID();
    const failures = [];
    const dialogs = [];
    const attempts = [];
    const events = [];
    const attachments = [];
    let ocrCalls = 0;
    let savedRequest = null;
    let releaseSave;
    const saveGate = new Promise((resolve) => { releaseSave = resolve; });
    let markSaveStarted;
    const saveStarted = new Promise((resolve) => { markSaveStarted = resolve; });

    await context.addInitScript(({ existingRequestId }) => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', 'tienda');
        if (existingRequestId) localStorage.setItem('solicitudBorradorBackendSmolbox', JSON.stringify({ backendId: existingRequestId }));
    }, { existingRequestId: existing ? requestId : null });

    await context.route('**/api/v1/**', async (route) => {
        const request = route.request();
        const path = new URL(request.url()).pathname;
        let data = {};
        let status = 200;
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: 'tienda', tienda: 'T001' };
        else if (path.endsWith('/frontend/capturas/me')) status = 201;
        else if (/\/capturas\/[^/]+\/eventos\/me$/.test(path)) {
            events.push(request.postDataJSON());
            status = 201;
        } else if (path.endsWith('/cfdi/ocr-preview')) {
            ocrCalls += 1;
            data = {
                extracted_total: '250.00', extracted_date: '2026-08-07',
                suggested_cfdi_uuid: documentType === 'factura' ? fiscalUuid : null,
                verification_token: 'test-ocr', checksum_sha256: 'test-checksum',
            };
        } else if (path.endsWith('/cfdi/parse')) data = {
            uuid: fiscalUuid, total: '123.45', subtotal: '106.42', tax_amount: '17.03',
            tax_rate: '16', currency: 'MXN', issued_at: '2026-08-13T12:00:00',
        };
        else if (/\/cfdi\/uuid\/[^/]+\/availability$/.test(path)) data = { is_available: true };
        else if (request.method() === 'POST' && (
            path.endsWith('/frontend/solicitudes/me') || path.endsWith(`/solicitudes/${requestId}/gastos/me`)
        )) {
            const body = request.postDataJSON();
            const expense = body.gastos?.[0] || body;
            attempts.push({ path, body, expense });
            markSaveStarted();
            if (pauseSave) await saveGate;
            if (failOnce && attempts.length === 1) {
                status = 503;
                data = { detail: 'Error de prueba al guardar.' };
            } else {
                savedRequest = {
                    backendId: requestId, id: 'T001-PRUEBA', folio: 'T001-PRUEBA', tienda: 'T001',
                    status: 'Borrador', backendStatus: 'draft',
                    gastos: [{ backendId: expenseId, id: expenseId, tipo: expense.categoria, monto: Number(expense.monto),
                        fecha: expense.fecha, folio: expense.folio, facturas: 1 }],
                };
                data = savedRequest;
                status = 201;
            }
        } else if (/\/expenses\/[^/]+\/attachments$/.test(path) || /\/expenses\/[^/]+\/cfdi\/validate$/.test(path)) {
            attachments.push(request.postData());
            data = { is_valid: true };
            status = 201;
        } else if (path.endsWith(`/solicitudes/${requestId}/me`)) data = savedRequest || {
            backendId: requestId, id: 'T001-PRUEBA', backendStatus: 'draft', gastos: [],
        };
        else if (path.endsWith('/frontend/bandeja/me') || path.endsWith('/frontend/historico/me') || path.endsWith('/audit-events')) data = [];
        else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });

    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));
    page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
    await page.goto(`${baseURL}/gasto/nuevo`);
    await page.getByRole('heading', { name: 'A\u00f1adir Gasto', exact: true }).waitFor();
    const date = page.getByPlaceholder('DD/MM/AAAA');
    const amount = page.getByPlaceholder('Ej. 123.45');
    const folio = page.getByPlaceholder('Ej. 12345678-ABCD-1234-ABCD-1234567890AB');
    const add = page.getByRole('button', { name: addName, exact: true });
    const summary = page.getByRole('dialog', { name: 'RESUMEN DEL GASTO' });
    const confirm = summary.getByRole('button', { name: confirmName, exact: true });
    const checkbox = summary.getByRole('checkbox');

    async function fillAndValidate() {
        await date.fill('13/08/2026');
        await amount.fill('123.45');
        if (documentType !== 'factura') {
            await page.getByRole('radio', { name: documentType === 'vale' ? 'Cargar Vale' : 'Cargar Recibo' }).check();
        }
        const fileIndex = ['factura', 'vale', 'recibo'].indexOf(documentType);
        await page.locator('input[type=file]').nth(fileIndex).setInputFiles({
            name: xml ? 'test.xml' : 'scan.pdf', mimeType: xml ? 'application/xml' : 'application/pdf',
            buffer: Buffer.from(xml ? '<test/>' : '%PDF-1.4\ncontent\n%%EOF'),
        });
        if (xml) {
            await page.waitForFunction(() => document.querySelector('input[placeholder^="Ej. 12345678"]').value !== '');
            await page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        }
        await page.getByRole('button', { name: 'Validar Gasto', exact: true }).click();
        await page.waitForFunction(() => [...document.querySelectorAll('button')]
            .find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
        if (documentType === 'factura' && !xml) await page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        assert.deepEqual(dialogs, [], 'existing validation warnings remain non-blocking');
    }

    return {
        context, page, date, amount, folio, add, summary, confirm, checkbox, fillAndValidate,
        failures, dialogs, attempts, events, attachments, saveStarted, releaseSave,
        ocrCalls: () => ocrCalls,
    };
}

async function checkSummaryLayout(page) {
    const layout = await page.locator('dialog').evaluate((dialog) => {
        const bounds = dialog.getBoundingClientRect();
        return {
            left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom,
            width: window.innerWidth, height: window.innerHeight,
            overflow: dialog.scrollWidth > dialog.clientWidth,
            valuesFit: [...dialog.querySelectorAll('dd')].every((value) => value.scrollWidth <= value.clientWidth),
        };
    });
    assert.ok(layout.left >= 0 && layout.right <= layout.width, 'dialog fits horizontally');
    assert.ok(layout.top >= 0 && layout.bottom <= layout.height, 'dialog fits vertically');
    assert.equal(layout.overflow, false, 'dialog has no horizontal overflow');
    assert.equal(layout.valuesFit, true, 'full UUID and amounts fit without clipping');
}

try {
    const invoice = await openForm({ pauseSave: true });
    await invoice.add.click();
    assert.equal(invoice.dialogs.at(-1), 'Debes cargar la factura antes de a\u00f1adir el gasto.');
    assert.equal(await invoice.summary.count(), 0, 'validation errors do not open the summary');
    invoice.dialogs.length = 0;
    await invoice.fillAndValidate();
    await invoice.add.click();
    await invoice.summary.waitFor();
    assert.equal(invoice.attempts.length, 0);
    assert.equal(invoice.attachments.length, 0);
    assert.equal(await invoice.checkbox.isChecked(), false);
    assert.equal(await invoice.confirm.isDisabled(), true);
    assert.equal(await invoice.summary.locator('dd').nth(0).innerText(), '13/08/2026');
    assert.equal(await invoice.summary.locator('dd').nth(1).innerText(), '$123.45');
    assert.equal(await invoice.summary.locator('dd').nth(2).innerText(), fiscalUuid);
    assert.equal(await invoice.checkbox.evaluate((element) => document.activeElement === element), true, 'dialog receives keyboard focus');
    await invoice.page.keyboard.press('Shift+Tab');
    assert.equal(await invoice.summary.evaluate((dialog) => dialog.contains(document.activeElement)), true, 'keyboard focus stays inside the modal');
    await checkSummaryLayout(invoice.page);
    await invoice.page.screenshot({ path: '/tmp/smolbox-expense-confirmation-desktop.png', fullPage: true });

    for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
        await invoice.page.setViewportSize(viewport);
        await checkSummaryLayout(invoice.page);
        await invoice.page.screenshot({ path: `/tmp/smolbox-expense-confirmation-mobile-${viewport.width}.png`, fullPage: true });
        await invoice.confirm.scrollIntoViewIfNeeded();
        const confirmBounds = await invoice.confirm.boundingBox();
        assert.ok(confirmBounds.y >= 0 && confirmBounds.y + confirmBounds.height <= viewport.height, 'confirmation remains reachable on small screens');
    }
    await invoice.page.setViewportSize({ width: 1366, height: 900 });
    await invoice.checkbox.check();
    await invoice.summary.getByRole('button', { name: 'Cancelar y Editar', exact: true }).click();
    assert.equal(await invoice.summary.count(), 0);
    assert.equal(invoice.attempts.length, 0);
    assert.equal(await invoice.add.evaluate((button) => document.activeElement === button), true, 'cancel restores keyboard focus');
    assert.equal(await invoice.date.inputValue(), '13/08/2026');
    assert.equal(await invoice.amount.inputValue(), '123.45');
    assert.equal(await invoice.folio.inputValue(), fiscalUuid);
    assert.equal(await invoice.page.locator('input[type=file]').first().evaluate((input) => input.files[0]?.name), 'scan.pdf');

    await invoice.amount.fill('99.90');
    await invoice.add.click();
    await invoice.summary.waitFor();
    assert.equal(await invoice.summary.locator('dd').nth(1).innerText(), '$99.90');
    assert.equal(await invoice.checkbox.isChecked(), false, 'editing resets the acknowledgement');
    await invoice.page.keyboard.press('Escape');
    assert.equal(await invoice.summary.count(), 0, 'Escape returns to editing without saving');
    await invoice.add.click();
    await invoice.summary.waitFor();
    assert.equal(await invoice.checkbox.isChecked(), false);
    await invoice.checkbox.check();
    await invoice.confirm.evaluate((button) => { button.click(); button.click(); });
    await invoice.saveStarted;
    assert.equal(invoice.attempts.length, 1, 'double click submits only once');
    assert.equal(await invoice.summary.getByRole('button', { name: 'Guardando...', exact: true }).isDisabled(), true);
    assert.equal(await invoice.summary.getByRole('button', { name: 'Cancelar y Editar', exact: true }).isDisabled(), true);
    assert.equal(await invoice.checkbox.isDisabled(), true);
    await invoice.page.keyboard.press('Escape');
    assert.equal(await invoice.summary.count(), 1, 'cannot dismiss while saving');
    invoice.releaseSave();
    await invoice.page.waitForURL('**/solicitud/nueva');
    assert.equal(invoice.attempts.length, 1);
    assert.equal(invoice.attempts[0].expense.monto, '99.9');
    assert.equal(invoice.attempts[0].expense.fecha, '13/08/2026');
    assert.equal(invoice.attempts[0].expense.folio, fiscalUuid);
    assert.equal(invoice.attachments.length, 1);
    assert.equal(invoice.ocrCalls(), 1, 'reviewing or confirming does not rerun OCR');
    assert.equal(invoice.dialogs.at(-1), successMessage);
    assert.ok(invoice.events.some((event) => event.action === 'click' && event.label === 'Cancelar y Editar'), 'cancel is audited before saving');
    assert.ok(invoice.events.some((event) => event.action === 'click' && event.label === confirmName), 'confirmation is audited');
    assert.deepEqual(invoice.failures, []);
    await invoice.context.close();

    for (const scenario of [{ documentType: 'vale' }, { documentType: 'recibo', existing: true }, { xml: true }]) {
        const form = await openForm(scenario);
        await form.fillAndValidate();
        await form.add.click();
        await form.summary.waitFor();
        assert.equal(form.attempts.length, 0);
        assert.equal(await form.confirm.isDisabled(), true);
        const isInvoice = !scenario.documentType;
        assert.equal(await form.summary.locator('dd').nth(2).innerText(), isInvoice ? fiscalUuid : 'No aplica');
        if (!isInvoice) {
            assert.ok((await form.summary.innerText()).includes(scenario.documentType === 'vale' ? 'Monto del Vale:' : 'Monto del Recibo:'));
        }
        await form.checkbox.check();
        await form.confirm.click();
        await form.page.waitForURL('**/solicitud/nueva');
        assert.equal(form.attempts.length, 1);
        assert.equal(form.attempts[0].expense.monto, '123.45');
        assert.ok(form.attempts[0].path.endsWith(scenario.existing ? '/gastos/me' : '/solicitudes/me'));
        assert.equal(form.attachments.length, 1);
        assert.equal(form.dialogs.at(-1), successMessage);
        assert.deepEqual(form.failures, []);
        await form.context.close();
    }

    const failed = await openForm({ documentType: 'vale', failOnce: true });
    await failed.fillAndValidate();
    await failed.add.click();
    await failed.summary.waitFor();
    await failed.checkbox.check();
    await failed.confirm.click();
    await failed.page.getByText('Error de prueba al guardar.', { exact: true }).waitFor();
    assert.equal(failed.dialogs.at(-1), 'Error de prueba al guardar.');
    assert.equal(await failed.summary.count(), 0);
    assert.equal(await failed.amount.inputValue(), '123.45');
    assert.equal(failed.attachments.length, 0);
    await failed.add.click();
    await failed.summary.waitFor();
    assert.equal(await failed.checkbox.isChecked(), false, 'a failed save requires fresh confirmation');
    await failed.checkbox.check();
    await failed.confirm.click();
    await failed.page.waitForURL('**/solicitud/nueva');
    assert.equal(failed.attempts.length, 2);
    assert.equal(failed.attachments.length, 1);
    assert.equal(failed.dialogs.at(-1), successMessage);
    assert.deepEqual(failed.failures, []);
    await failed.context.close();
    console.log('Browser checks passed: validation, summary, cancel/edit, acknowledgement, keyboard, responsive layout, double click, PDF/XML/vale/recibo, existing draft, audit and save errors.');
} finally {
    await browser.close();
}
