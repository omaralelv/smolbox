import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const fiscalUuid = 'AABBCCDD-1234-4ABC-8DEF-001122334455';
const successMessage = '\u00a1Gasto guardado exitosamente en la solicitud!';
const confirmName = 'Confirmar y A\u00f1adir';
const addName = 'A\u00f1adir';

async function openForm({ documentType = 'factura', xml = false, existing = false, pauseSave = false, failOnce = false, ocr = {}, cfdi = {} } = {}) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const requestId = randomUUID();
    const expenseId = randomUUID();
    const failures = [];
    const dialogs = [];
    const attempts = [];
    const events = [];
    const attachments = [];
    let ocrCalls = 0;
    let uuidAvailable = true;
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
                ...ocr,
            };
        } else if (path.endsWith('/cfdi/parse')) data = {
            uuid: fiscalUuid, total: '123.45', subtotal: '106.42', tax_amount: '17.03',
            tax_rate: '16', currency: 'MXN', issued_at: '2026-08-13T12:00:00',
            ...cfdi,
        };
        else if (/\/cfdi\/uuid\/[^/]+\/availability$/.test(path)) data = { is_available: uuidAvailable };
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
        if (documentType === 'factura' && !xml) {
            if (!await folio.inputValue()) await folio.fill(fiscalUuid);
            await page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        }
        assert.deepEqual(dialogs, [], 'existing validation warnings remain non-blocking');
    }

    return {
        context, page, date, amount, folio, add, summary, confirm, checkbox, fillAndValidate,
        failures, dialogs, attempts, events, attachments, saveStarted, releaseSave,
        ocrCalls: () => ocrCalls,
        setUuidAvailable: (value) => { uuidAvailable = value; },
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
            values: [...dialog.querySelectorAll('dd')].map((value) => ({ width: value.clientWidth, scrollWidth: value.scrollWidth })),
        };
    });
    assert.ok(layout.left >= 0 && layout.right <= layout.width, 'dialog fits horizontally');
    assert.ok(layout.top >= 0 && layout.bottom <= layout.height, 'dialog fits vertically');
    assert.equal(layout.overflow, false, 'dialog has no horizontal overflow');
    if (!layout.valuesFit) await page.screenshot({ path: `/tmp/smolbox-expense-confirmation-overflow-${layout.width}.png`, fullPage: true });
    assert.equal(layout.valuesFit, true, `full UUID and amounts fit without clipping: ${JSON.stringify(layout)}`);
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

    for (const scenario of [{ documentType: 'vale' }, { documentType: 'recibo', existing: true }, { xml: true, cfdi: { issued_at: '2026-08-07T12:00:00' } }]) {
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

    const matchedOcr = { extracted_total: '123.45', extracted_date: '2026-08-13' };
    for (const scenario of [
        { ocr: matchedOcr, pauseSave: true },
        { xml: true },
        { documentType: 'vale', ocr: matchedOcr },
        { documentType: 'recibo', ocr: matchedOcr, existing: true },
    ]) {
        const form = await openForm(scenario);
        await form.fillAndValidate();
        await form.date.fill('13/8/2026');
        await form.amount.fill('123.450');
        if (!scenario.documentType) {
            await form.folio.fill(` ${fiscalUuid.toLowerCase()} `);
            await form.page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        }
        await form.add.evaluate((button) => { button.click(); button.click(); });
        await form.saveStarted;
        assert.equal(await form.summary.count(), 0, 'matching fields save without the additional confirmation');
        if (scenario.pauseSave) {
            assert.equal(await form.page.getByRole('button', { name: 'Guardando...', exact: true }).isDisabled(), true);
            assert.equal(await form.amount.isDisabled(), true, 'direct saving also freezes the prepared data');
            form.releaseSave();
        }
        await form.page.waitForURL('**/solicitud/nueva');
        assert.equal(form.attempts.length, 1, 'direct saving is protected against double clicks');
        assert.equal(form.attachments.length, 1);
        assert.equal(form.attempts[0].expense.monto, '123.45');
        assert.equal(form.attempts[0].expense.fecha, '13/8/2026');
        assert.equal(form.attempts[0].expense.folio, scenario.documentType ? null : fiscalUuid);
        assert.equal(form.ocrCalls(), scenario.xml ? 0 : 1, 'direct saving reuses the document read');
        assert.equal(form.dialogs.at(-1), successMessage);
        assert.equal(form.events.some((event) => event.action === 'click' && event.label === confirmName), false);
        assert.deepEqual(form.failures, []);
        await form.context.close();
    }

    for (const scenario of [
        { name: 'amount edited after validation', edit: 'amount' },
        { name: 'date edited after validation', edit: 'date' },
        { name: 'fiscal UUID edited after validation', edit: 'folio' },
        { name: 'missing amount', ocr: { extracted_total: null } },
        { name: 'missing date', ocr: { extracted_date: null } },
        { name: 'missing UUID with manual entry', ocr: { suggested_cfdi_uuid: null } },
        { name: 'invalid OCR UUID with manual entry', ocr: { suggested_cfdi_uuid: '12345' } },
        { name: 'XML amount edited after validation', xml: true, edit: 'amount' },
        { name: 'XML fiscal UUID edited after validation', xml: true, edit: 'folio' },
        { name: 'missing XML date', xml: true, cfdi: { issued_at: null } },
        { name: 'vale missing date', documentType: 'vale', ocr: { extracted_date: null } },
        { name: 'recibo missing amount', documentType: 'recibo', ocr: { extracted_total: null } },
    ]) {
        const form = await openForm({ ...scenario, ocr: { ...matchedOcr, ...scenario.ocr } });
        await form.fillAndValidate();
        if (scenario.edit === 'amount') await form.amount.fill('123.46');
        if (scenario.edit === 'date') await form.date.fill('14/08/2026');
        if (scenario.edit === 'folio') {
            await form.folio.fill('AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA');
            await form.page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        }
        await form.add.click();
        await form.summary.waitFor();
        assert.equal(form.attempts.length, 0, scenario.name);
        assert.equal(await form.confirm.isDisabled(), true, scenario.name);
        await form.checkbox.check();
        await form.confirm.click();
        await form.page.waitForURL('**/solicitud/nueva');
        assert.equal(form.attempts.length, 1, scenario.name);
        assert.equal(form.attempts[0].expense.monto, scenario.edit === 'amount' ? '123.46' : '123.45');
        if (scenario.edit === 'folio') assert.equal(form.attempts[0].expense.folio, 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA');
        assert.deepEqual(form.failures, [], scenario.name);
        await form.context.close();
    }

    const blocked = await openForm({ ocr: matchedOcr });
    await blocked.fillAndValidate();
    await blocked.date.fill('31/02/2026');
    const invalidDateDialog = blocked.page.waitForEvent('dialog');
    await blocked.add.click();
    assert.ok((await invalidDateDialog).message().includes('Corrobora que la fecha ingresada'));
    assert.equal(blocked.attempts.length, 0);
    assert.equal(await blocked.summary.count(), 0, 'an invalid date remains a blocking error');
    await blocked.date.fill('13/08/2026');
    blocked.setUuidAvailable(false);
    const duplicateDialog = blocked.page.waitForEvent('dialog');
    await blocked.add.click();
    assert.ok((await duplicateDialog).message().includes('ya est\u00e1 registrado en otro gasto'));
    assert.equal(blocked.attempts.length, 0);
    assert.equal(await blocked.summary.count(), 0, 'duplicate UUIDs cannot be overridden by confirmation');
    await blocked.page.locator('input[type=file]').first().setInputFiles({
        name: 'different.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\ndifferent\n%%EOF'),
    });
    const unreadFileDialog = blocked.page.waitForEvent('dialog');
    await blocked.add.click();
    assert.equal((await unreadFileDialog).message(), 'Primero presiona "Validar Gasto" para leer la factura PDF con OCR.');
    assert.equal(blocked.attempts.length, 0, 'another file cannot reuse a previous matching OCR result');
    assert.equal(await blocked.summary.count(), 0);
    assert.deepEqual(blocked.failures, []);
    await blocked.context.close();

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

    const failedDirect = await openForm({ documentType: 'vale', ocr: matchedOcr, failOnce: true });
    await failedDirect.fillAndValidate();
    await failedDirect.add.click();
    await failedDirect.page.getByText('Error de prueba al guardar.', { exact: true }).waitFor();
    assert.equal(await failedDirect.summary.count(), 0);
    assert.equal(await failedDirect.amount.inputValue(), '123.45');
    assert.equal(failedDirect.attachments.length, 0);
    await failedDirect.add.click();
    await failedDirect.page.waitForURL('**/solicitud/nueva');
    assert.equal(failedDirect.attempts.length, 2);
    assert.equal(failedDirect.attachments.length, 1);
    assert.equal(failedDirect.dialogs.at(-1), successMessage);
    assert.deepEqual(failedDirect.failures, []);
    await failedDirect.context.close();
    console.log('Browser checks passed: conditional confirmation for PDF/XML/vale/recibo, individual mismatches, missing fields, current data/file comparison, direct and confirmed saves, double clicks, errors, audit, keyboard and responsive layout.');
} finally {
    await browser.close();
}
