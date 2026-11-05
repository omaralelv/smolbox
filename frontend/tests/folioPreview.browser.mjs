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
const file = (text = 'first') => ({ name: 'scan.pdf', mimeType: 'application/pdf', buffer: Buffer.from(`%PDF-1.4\n${text}\n%%EOF`) });

async function openForm(viewport, { preview = true, pauseOcr = false, brokenImage = false } = {}) {
    const context = await browser.newContext({ viewport });
    const errors = [], dialogs = [], saves = [], attachments = [];
    let calls = 0, saved = false, imageData;
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    const payload = () => ({ backendId: requestId, id: 'T001-TEST', folio: 'T001-TEST', tienda: 'T001',
        status: 'Borrador', backendStatus: 'draft', montoTotal: saved ? 100 : 0,
        gastos: saved ? [{ id: expenseId, backendId: expenseId, tipo: 'Papeler\u00eda', fecha: '07/08/2026',
            monto: 100, folio: uuid, facturas: 1, canAddObservation: true }] : [] });
    await context.addInitScript(() => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', 'tienda');
    });
    await context.route('**/api/v1/**', async (route) => {
        const req = route.request();
        const path = new URL(req.url()).pathname;
        let status = 200, data = {};
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: 'tienda', stores: [store], activeStore: store };
        else if (/\/frontend\/capturas\/me$|\/capturas\/[^/]+\/eventos\/me$/.test(path)) status = 201;
        else if (path.endsWith('/cfdi/ocr-preview')) {
            calls += 1;
            if (pauseOcr) await gate;
            data = { suggested_cfdi_uuid: uuid, extracted_total: '100.00', extracted_date: '2026-08-07',
                verification_token: 'ocr-token', checksum_sha256: 'original-checksum',
                ...(preview ? { folio_preview: { uuid, page: 1, image_data_url: brokenImage ? 'data:image/png;base64,bad' : imageData } } : {}),
            };
        } else if (/\/cfdi\/uuid\/[^/]+\/availability$/.test(path)) data = { is_available: true };
        else if (path.endsWith(`/solicitudes/tienda/${store.id}/borrador/me`)) data = payload();
        else if (path.endsWith(`/solicitudes/${requestId}/gastos/me`)) {
            saves.push(req.postDataJSON()); saved = true; data = payload(); status = 201;
        } else if (path.endsWith(`/solicitudes/${requestId}/me`)) data = payload();
        else if (/\/expenses\/[^/]+\/attachments$/.test(path)) {
            attachments.push(req.postData()); status = 201;
        } else if (path.endsWith('/frontend/bandeja/me') || path.endsWith('/frontend/historico/me') || path.endsWith('/audit-events')) data = [];
        else { errors.push(`Unexpected API ${req.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
    await page.goto(`${baseURL}/gasto/nuevo`);
    await page.getByRole('heading', { name: 'A\u00f1adir Gasto', exact: true }).waitFor();
    imageData = await page.evaluate((folio) => {
        const canvas = document.createElement('canvas');
        canvas.width = 820; canvas.height = 60;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'white'; ctx.fillRect(0, 0, 820, 60);
        ctx.fillStyle = 'black'; ctx.font = '28px monospace'; ctx.fillText(folio, 14, 40);
        return canvas.toDataURL('image/png');
    }, uuid);
    await page.getByPlaceholder('DD/MM/AAAA').fill('07/08/2026');
    await page.getByPlaceholder('Ej. 123.45').fill('100');
    const input = page.locator('input[type=file]').first();
    await input.setInputFiles(file());
    const validate = page.getByRole('button', { name: 'Validar Gasto', exact: true });
    const folio = page.getByPlaceholder('Ej. 12345678-ABCD-1234-ABCD-1234567890AB');
    async function validateExpense() {
        await validate.click();
        await page.waitForFunction(() => [...document.querySelectorAll('button')]
            .find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
    }
    return { context, page, input, validate, folio, validateExpense, errors, dialogs, saves, attachments, release, calls: () => calls };
}

try {
    for (const viewport of [{ width: 1366, height: 900 }, { width: 390, height: 844 }]) {
        const s = await openForm(viewport);
        await s.validateExpense();
        const thumb = s.page.getByRole('button', { name: 'Ampliar folio detectado' });
        await thumb.waitFor();
        const image = thumb.locator('img').first();
        assert.ok(await image.evaluate((img) => img.complete && img.naturalWidth === 820));
        const inputBox = await s.folio.boundingBox(), imageBox = await thumb.boundingBox();
        assert.ok(imageBox.y >= inputBox.y + inputBox.height, 'preview is below the fiscal UUID input');
        assert.ok(imageBox.width <= inputBox.width + 110, 'preview does not enlarge the input group');
        await thumb.scrollIntoViewIfNeeded();
        const visibleBox = await thumb.boundingBox();
        assert.ok(visibleBox.x >= 0 && visibleBox.x + visibleBox.width <= viewport.width + 1, 'thumbnail fits the viewport');
        await s.page.screenshot({ path: `/private/tmp/smolbox-folio-${viewport.width}.png` });
        await thumb.click();
        const modal = s.page.getByRole('dialog', { name: 'Folio fiscal ampliado' });
        await modal.waitFor();
        const modalBox = await modal.boundingBox();
        assert.ok(modalBox.x >= 0 && modalBox.x + modalBox.width <= viewport.width + 1);
        assert.ok(modalBox.y >= 0 && modalBox.height <= viewport.height);
        await s.page.screenshot({ path: `/private/tmp/smolbox-folio-expanded-${viewport.width}.png` });
        await s.page.keyboard.press('Escape');
        assert.equal(await modal.isVisible(), false);
        assert.equal(await s.folio.inputValue(), uuid, 'opening the preview does not change the UUID');
        assert.equal(await s.page.getByRole('button', { name: 'Confirmar', exact: true }).count(), 1, 'preview does not confirm the UUID');
        await s.validateExpense();
        assert.equal(s.calls(), 1, 'revalidating reuses OCR without extra AWS calls');
        assert.equal(await thumb.isVisible(), true);
        await s.page.getByRole('button', { name: 'Confirmar', exact: true }).click();
        await s.page.getByRole('button', { name: 'A\u00f1adir', exact: true }).click();
        await s.page.waitForURL('**/solicitud/nueva');
        assert.equal(s.saves.length, 1);
        assert.equal(s.saves[0].cfdiUuid, uuid);
        assert.ok(!JSON.stringify(s.saves).includes('image_data_url'));
        assert.equal(s.attachments.length, 1);
        assert.ok(s.attachments[0].includes('ocr-token'));
        assert.ok(await s.page.evaluate(() => !Object.values(localStorage).some((value) => value.includes('image_data_url'))));
        assert.deepEqual(s.dialogs, ['\u00a1Gasto guardado exitosamente en la solicitud!']);
        assert.deepEqual(s.errors, []);
        await s.context.close();
    }
    const replacement = await openForm({ width: 1366, height: 900 });
    await replacement.validateExpense();
    await replacement.page.getByRole('button', { name: 'Ampliar folio detectado' }).click();
    await replacement.page.getByRole('button', { name: 'Cerrar folio ampliado' }).click();
    await replacement.input.setInputFiles(file('other'));
    assert.equal(await replacement.page.getByRole('button', { name: 'Ampliar folio detectado' }).count(), 0);
    assert.equal(await replacement.folio.inputValue(), '');
    await replacement.validateExpense();
    assert.equal(replacement.calls(), 2, 'same filename/size does not reuse another File object');
    await replacement.page.getByRole('radio', { name: 'Cargar Vale' }).check();
    assert.equal(await replacement.page.getByRole('button', { name: 'Ampliar folio detectado' }).count(), 0);
    assert.equal(await replacement.folio.inputValue(), 'N/A');
    assert.deepEqual(replacement.errors, []);
    await replacement.context.close();

    for (const options of [{ preview: false }, { brokenImage: true }]) {
        const s = await openForm({ width: 1366, height: 900 }, options);
        await s.validateExpense();
        await s.page.waitForTimeout(100);
        assert.equal(await s.page.getByRole('button', { name: 'Ampliar folio detectado' }).count(), 0);
        assert.equal(await s.folio.inputValue(), uuid);
        assert.deepEqual(s.dialogs, []);
        assert.deepEqual(s.errors, []);
        await s.context.close();
    }

    const delayed = await openForm({ width: 1366, height: 900 }, { pauseOcr: true });
    const ocrStarted = delayed.page.waitForRequest('**/cfdi/ocr-preview');
    await delayed.validate.click();
    await ocrStarted;
    await delayed.input.setInputFiles(file('other'));
    delayed.release();
    await delayed.page.waitForFunction(() => [...document.querySelectorAll('button')]
        .find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
    assert.equal(await delayed.folio.inputValue(), '', 'late OCR cannot overwrite a newly selected file');
    assert.equal(await delayed.page.getByRole('button', { name: 'Ampliar folio detectado' }).count(), 0);
    assert.deepEqual(delayed.dialogs, []);
    assert.deepEqual(delayed.errors, []);
    await delayed.context.close();
    console.log('Folio preview: desktop/mobile, enlargement, cache reuse, manual confirmation/save, transient image, replacement, type switch, missing/broken image and delayed OCR passed.');
} finally {
    await browser.close();
}
