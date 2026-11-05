import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const uuid = '11111111-2222-3333-4444-AAAAAAAAAAAA';
const store = { id: '11111111-1111-4111-8111-111111111111', code: 'T001', name: 'Centro' };
const requestId = '22222222-2222-4222-8222-222222222222';
const expenseId = '33333333-3333-4333-8333-333333333333';
const marks = [
    { field: 'date', page: 2, left: .095, top: .14, width: .5, height: .025 },
    { field: 'total', page: 2, left: .095, top: .198, width: .5, height: .025 },
    { field: 'folio', page: 2, left: .095, top: .255, width: .8, height: .025 },
];

function fixturePdf(label = 'PRUEBA') {
    const stream = (content) => `<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`;
    const objects = [
        '<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>',
        stream(`BT /F1 20 Tf 60 730 Td (COMPROBANTE ${label}) Tj 0 -40 Td (Pagina 1 de 2) Tj ET`),
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>',
        stream(`BT /F1 16 Tf 60 730 Td (COMERCIAL IAC) Tj /F1 12 Tf 0 -60 Td (Fecha: 07/08/2026) Tj 0 -45 Td (TOTAL: $100.00) Tj 0 -45 Td (Folio Fiscal: ${uuid}) Tj ET`),
        '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ];
    return serializePdf(objects);
}

function serializePdf(objects) {
    const parts = [Buffer.from('%PDF-1.4\n')], offsets = [0];
    let length = parts[0].length;
    for (const [index, object] of objects.entries()) {
        offsets.push(length);
        const section = Buffer.concat([Buffer.from(`${index + 1} 0 obj\n`), Buffer.isBuffer(object) ? object : Buffer.from(object), Buffer.from('\nendobj\n')]);
        parts.push(section); length += section.length;
    }
    let content = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    for (const value of offsets.slice(1)) content += `${String(value).padStart(10, '0')} 00000 n \n`;
    parts.push(Buffer.from(`${content}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${length}\n%%EOF`));
    return Buffer.concat(parts);
}

async function imagePdf(page) {
    const data = await page.evaluate(() => {
        const image = document.createElement('canvas'); image.width = 612; image.height = 792;
        const context = image.getContext('2d'); context.fillStyle = 'white'; context.fillRect(0, 0, 612, 792);
        context.fillStyle = 'black'; context.font = '28px sans-serif'; context.fillText('RECIBO ESCANEADO', 50, 100);
        context.font = '20px sans-serif'; context.fillText('TOTAL $100.00', 50, 170);
        return image.toDataURL('image/jpeg').split(',')[1];
    });
    const jpeg = Buffer.from(data, 'base64');
    const operators = 'q 612 0 0 792 0 0 cm /Image0 Do Q';
    return serializePdf([
        '<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Image0 5 0 R >> >> /Contents 4 0 R >>',
        `<< /Length ${operators.length} >>\nstream\n${operators}\nendstream`,
        Buffer.concat([Buffer.from(`<< /Type /XObject /Subtype /Image /Width 612 /Height 792 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`), jpeg, Buffer.from('\nendstream')]),
    ]);
}

async function openForm(viewport, { noMarks = false, failOcr = false, pauseOcr = false, documentType = 'factura', scanned = false, emptyFields = false } = {}) {
    const context = await browser.newContext({ viewport });
    const errors = [], dialogs = [], saves = [], attachments = [], consoleMessages = [];
    let calls = 0, saved = false, release;
    const gate = new Promise((resolve) => { release = resolve; });
    const payload = () => ({ backendId: requestId, id: 'T001-TEST', folio: 'T001-TEST', tienda: 'T001',
        status: 'Borrador', backendStatus: 'draft', montoTotal: saved ? 100 : 0,
        gastos: saved ? [{ id: expenseId, backendId: expenseId, tipo: 'Papeler\u00eda', fecha: '07/08/2026',
            monto: 100, folio: documentType === 'factura' ? uuid : 'N/A', facturas: 1, canAddObservation: true }] : [] });
    await context.addInitScript(() => {
        localStorage.setItem('smolboxApiToken', 'test-token'); localStorage.setItem('smolboxFrontendRole', 'tienda');
    });
    await context.route('**/api/v1/**', async (route) => {
        const req = route.request(), path = new URL(req.url()).pathname;
        let status = 200, data = {};
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: 'tienda', stores: [store], activeStore: store };
        else if (/\/frontend\/capturas\/me$|\/capturas\/[^/]+\/eventos\/me$/.test(path)) status = 201;
        else if (path.endsWith('/cfdi/ocr-preview')) {
            calls += 1; if (pauseOcr) await gate;
            if (failOcr) { status = 502; data = { detail: { code: 'OCR_UNREADABLE_DOCUMENT', message: 'No se pudo leer el documento con OCR.' } }; }
            else data = { suggested_cfdi_uuid: documentType === 'factura' ? uuid : null,
                extracted_total: '100.00', extracted_date: '2026-08-07',
                verification_token: 'ocr-token', checksum_sha256: 'original-checksum',
                ...(noMarks ? {} : { document_highlights: marks.filter((item) => documentType === 'factura' || item.field !== 'folio') }),
                ...(emptyFields ? { suggested_cfdi_uuid: null, extracted_total: null, extracted_date: null, document_highlights: [] } : {}),
            };
        } else if (/\/cfdi\/uuid\/[^/]+\/availability$/.test(path)) data = { is_available: true };
        else if (path.endsWith(`/solicitudes/tienda/${store.id}/borrador/me`)) data = payload();
        else if (path.endsWith(`/solicitudes/${requestId}/gastos/me`)) { saves.push(req.postDataJSON()); saved = true; data = payload(); status = 201; }
        else if (path.endsWith(`/solicitudes/${requestId}/me`)) data = payload();
        else if (/\/expenses\/[^/]+\/attachments$/.test(path)) { attachments.push(req.postData()); status = 201; }
        else if (path.endsWith('/frontend/bandeja/me') || path.endsWith('/frontend/historico/me') || path.endsWith('/audit-events')) data = [];
        else { errors.push(`Unexpected API ${req.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => { if (message.type() === 'error' || message.type() === 'warn') consoleMessages.push(message.text()); });
    page.on('response', (response) => {
        if (response.status() >= 400 && /\/pdfjs\/|pdf\.worker/.test(response.url())) errors.push(`PDF resource unavailable: ${response.url()}`);
    });
    page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
    await page.goto(`${baseURL}/gasto/nuevo`);
    await page.getByRole('heading', { name: 'A\u00f1adir Gasto', exact: true }).waitFor();
    await page.getByPlaceholder('DD/MM/AAAA').fill('07/08/2026');
    await page.getByPlaceholder('Ej. 123.45').fill('100');
    if (documentType !== 'factura') await page.getByRole('radio', { name: documentType === 'vale' ? 'Cargar Vale' : 'Cargar Recibo' }).check();
    const input = page.locator('input[type=file]').nth(['factura', 'vale', 'recibo'].indexOf(documentType));
    await input.setInputFiles({ name: 'scan.pdf', mimeType: 'application/pdf', buffer: scanned ? await imagePdf(page) : fixturePdf() });
    const viewer = page.getByRole('region', { name: 'Vista previa del comprobante PDF' });
    const validate = page.getByRole('button', { name: 'Validar Gasto', exact: true });
    const folio = page.getByPlaceholder('Ej. 12345678-ABCD-1234-ABCD-1234567890AB');
    async function ready() {
        try { await page.locator('.pdf-document-sheet[aria-busy="false"]').waitFor(); }
        catch (error) {
            console.log({ viewer: await page.locator('.pdf-document-viewer').innerText(), errors, consoleMessages });
            await page.screenshot({ path: '/private/tmp/smolbox-pdf-failure.png', fullPage: true });
            throw error;
        }
        assert.ok(await page.locator('.pdf-document-sheet canvas').evaluate((canvas) => {
            const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
            for (let index = 0; index < pixels.length; index += 4) if (pixels[index] < 80 && pixels[index + 3] > 0) return true;
            return false;
        }), 'PDF canvas contains actual document text');
    }
    async function validateExpense() {
        await validate.click();
        await page.waitForFunction(() => [...document.querySelectorAll('button')].find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
    }
    return { context, page, viewer, input, validate, folio, ready, validateExpense, errors, dialogs, saves, attachments, release, calls: () => calls };
}

try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
        const s = await openForm(viewport);
        await s.ready();
        assert.equal(s.calls(), 0, 'PDF is visible before running OCR');
        assert.equal(await s.page.locator('[data-pdf-highlight]').count(), 0);
        assert.equal(await s.page.getByRole('button', { name: 'Ampliar folio detectado' }).count(), 0, 'old thumbnail removed');
        const pdfBox = await s.viewer.boundingBox(), formBox = await s.folio.boundingBox();
        if (viewport.width > 900) assert.ok(pdfBox.x + pdfBox.width <= formBox.x, 'PDF is to the left of the form');
        else assert.ok(pdfBox.y + pdfBox.height <= formBox.y, 'PDF is above the form on mobile');
        await s.validateExpense();
        await s.folio.focus();
        await s.ready();
        assert.equal(await s.page.getByLabel('P\u00e1gina del PDF', { exact: true }).inputValue(), '2');
        assert.equal(await s.page.locator('[data-pdf-highlight]').count(), 3);
        await s.page.screenshot({ path: `/private/tmp/smolbox-pdf-marks-${viewport.width}.png`, fullPage: true });
        assert.ok(await s.page.locator('[data-pdf-highlight]').evaluateAll((elements) => elements.every((element) => {
            const sheet = element.parentElement, canvas = sheet.querySelector('canvas');
            const x = Math.max(0, Math.floor(parseFloat(element.style.left) / 100 * canvas.width));
            const y = Math.max(0, Math.floor(parseFloat(element.style.top) / 100 * canvas.height));
            const w = Math.min(canvas.width - x, Math.floor(parseFloat(element.style.width) / 100 * canvas.width));
            const h = Math.min(canvas.height - y, Math.floor(parseFloat(element.style.height) / 100 * canvas.height));
            const data = canvas.getContext('2d').getImageData(x, y, w, h).data;
            return data.some((v, i) => i % 4 === 0 && v < 220);
        })), 'each yellow mark covers text in the PDF');
        const originalZoom = await s.viewer.getByLabel('Zoom del PDF').textContent();
        await s.viewer.getByRole('button', { name: 'Acercar PDF' }).click(); await s.ready();
        const zoomed = await s.viewer.getByLabel('Zoom del PDF').textContent();
        assert.notEqual(zoomed, originalZoom);
        await s.page.getByPlaceholder('Escribe aqu\u00ed notas adicionales sobre este gasto que creas necesarias...').fill('Nota de prueba');
        assert.equal(await s.viewer.getByLabel('Zoom del PDF').textContent(), zoomed, 'editing preserves zoom');
        assert.equal(await s.page.getByLabel('P\u00e1gina del PDF', { exact: true }).inputValue(), '2', 'editing preserves page');
        await s.viewer.getByRole('button', { name: 'Mostrar p\u00e1gina completa' }).click(); await s.ready();
        await s.page.screenshot({ path: `/private/tmp/smolbox-pdf-workspace-${viewport.width}.png`, fullPage: true });
        await s.viewer.getByRole('button', { name: 'Ampliar visor' }).click();
        const modal = s.page.getByRole('dialog', { name: 'Comprobante PDF ampliado' });
        await modal.waitFor(); await s.ready();
        assert.ok(await modal.getAttribute('data-audit-capture-id'), 'expanded tools retain capture auditing');
        const bounds = await modal.boundingBox(); assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= viewport.width);
        await s.page.screenshot({ path: `/private/tmp/smolbox-pdf-expanded-${viewport.width}.png` });
        await s.page.keyboard.press('Escape'); await s.viewer.waitFor(); await s.ready();
        assert.equal(await s.page.evaluate(() => document.getElementById('root').inert), false);
        await s.viewer.getByRole('button', { name: 'P\u00e1gina anterior' }).click(); await s.ready();
        assert.equal(await s.page.locator('[data-pdf-highlight]').count(), 0);
        await s.viewer.getByRole('button', { name: 'P\u00e1gina siguiente' }).click(); await s.ready();
        await s.validateExpense(); assert.equal(s.calls(), 1, 'revalidation does not add OCR calls');
        await s.page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        await s.page.getByRole('button', { name: 'A\u00f1adir', exact: true }).click();
        await s.page.waitForURL('**/solicitud/nueva');
        assert.equal(s.saves.length, 1); assert.equal(s.saves[0].cfdiUuid, uuid);
        assert.ok(!JSON.stringify(s.saves).includes('document_highlights'));
        assert.equal(s.attachments.length, 1); assert.ok(s.attachments[0].includes('ocr-token'));
        assert.deepEqual(s.dialogs, ['\u00a1Gasto guardado exitosamente en la solicitud!']);
        assert.deepEqual(s.errors, []); await s.context.close();
    }
    for (const options of [{ noMarks: true }, { failOcr: true }, { documentType: 'vale' }, { documentType: 'recibo' }]) {
        const s = await openForm({ width: 1366, height: 900 }, options);
        await s.ready(); await s.validateExpense();
        await s.viewer.getByRole('button', { name: 'P\u00e1gina siguiente' }).click(); await s.ready();
        assert.equal(await s.page.locator('[data-pdf-highlight]').count(), options.noMarks || options.failOcr ? 0 : 2);
        if (options.failOcr) assert.deepEqual(s.dialogs, ['No se pudo leer el documento con OCR.']);
        else assert.deepEqual(s.dialogs, []);
        assert.deepEqual(s.errors, []); await s.context.close();
    }
    const scan = await openForm({ width: 1366, height: 900 }, { scanned: true, noMarks: true });
    await scan.ready(); await scan.validateExpense();
    assert.equal(await scan.viewer.getByRole('button', { name: 'P\u00e1gina siguiente' }).isDisabled(), true);
    assert.equal(await scan.page.locator('[data-pdf-highlight]').count(), 0);
    await scan.viewer.getByRole('button', { name: 'Acercar PDF' }).click(); await scan.ready();
    assert.deepEqual(scan.errors, []); await scan.context.close();

    const empty = await openForm({ width: 1366, height: 900 }, { emptyFields: true });
    await empty.ready(); await empty.validateExpense();
    assert.equal(await empty.page.locator('[data-pdf-highlight]').count(), 0);
    await empty.folio.fill(uuid);
    await empty.page.getByRole('button', { name: 'Confirmar', exact: true }).click();
    await empty.page.getByRole('button', { name: 'A\u00f1adir', exact: true }).click();
    const summary = empty.page.getByRole('dialog', { name: 'RESUMEN DEL GASTO' });
    await summary.waitFor(); assert.equal(empty.saves.length, 0, 'missing fields still require double verification');
    await summary.getByRole('button', { name: 'Cancelar y Editar' }).click();
    await empty.ready();
    await empty.page.getByRole('button', { name: 'A\u00f1adir', exact: true }).click();
    await summary.getByRole('checkbox').check();
    await summary.getByRole('button', { name: 'Confirmar y A\u00f1adir' }).click();
    await empty.page.waitForURL('**/solicitud/nueva');
    assert.equal(empty.saves.length, 1); assert.equal(empty.calls(), 1);
    assert.deepEqual(empty.errors, []); await empty.context.close();

    const invalid = await openForm({ width: 1366, height: 900 });
    await invalid.ready();
    await invalid.input.setInputFiles({ name: 'invalid.pdf', mimeType: 'text/html', buffer: Buffer.from('<script>parent.pdfFileExecuted = true</script>') });
    const fallback = invalid.page.getByTitle('Comprobante PDF original');
    await fallback.waitFor();
    assert.equal(await invalid.page.evaluate(() => Boolean(window.pdfFileExecuted)), false);
    assert.equal(await fallback.evaluate(async (frame) => (await fetch(frame.src)).headers.get('content-type')), 'application/pdf');
    await invalid.context.close();

    const slow = await openForm({ width: 1366, height: 900 }, { pauseOcr: true });
    await slow.ready(); const started = slow.page.waitForRequest('**/cfdi/ocr-preview');
    await slow.validate.click(); await started;
    await slow.input.setInputFiles({ name: 'scan.pdf', mimeType: 'application/pdf', buffer: fixturePdf('OTRAPDF') });
    slow.release(); await slow.ready();
    await slow.page.waitForFunction(() => [...document.querySelectorAll('button')].find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
    assert.equal(await slow.folio.inputValue(), '');
    assert.equal(await slow.page.locator('[data-pdf-highlight]').count(), 0, 'old OCR cannot mark a different document');
    await slow.page.getByRole('radio', { name: 'Cargar Vale' }).check();
    assert.equal(await slow.viewer.count(), 0); assert.deepEqual(slow.errors, []); await slow.context.close();
    console.log('PDF viewer passed: actual two-page PDF before OCR, yellow marks, field navigation, zoom, paging, fullscreen, desktop/mobile, preserved save, no OCR/failed OCR, vale/recibo and late-response isolation.');
} finally { await browser.close(); }
