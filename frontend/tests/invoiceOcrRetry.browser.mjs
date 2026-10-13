import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const uuid = '99999999-9999-4999-8999-999999999999';
const scenarios = [
    { name: 'missing UUID', firstUuid: null, calls: 2 },
    { name: 'empty UUID', firstUuid: '', calls: 2 },
    { name: 'invalid UUID', firstUuid: '11950', calls: 2 },
    { name: 'complete invoice', firstUuid: uuid, calls: 1 },
    { name: 'manual UUID', firstUuid: null, calls: 1, manual: true },
    { name: 'vale', documentType: 'vale', calls: 1 },
    { name: 'recibo', documentType: 'recibo', calls: 1 },
];

try {
    for (const scenario of scenarios) {
        const documentType = scenario.documentType || 'factura';
        const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
        const failures = [];
        const dialogs = [];
        const creations = [];
        let ocrCalls = 0;
        await context.addInitScript(() => {
            localStorage.setItem('smolboxApiToken', 'test-token');
            localStorage.setItem('smolboxFrontendRole', 'tienda');
        });
        await context.route('**/api/v1/**', async (route) => {
            const request = route.request();
            const path = new URL(request.url()).pathname;
            let data = {};
            let status = 200;
            if (path.endsWith('/health')) data = { version: 'test' };
            else if (path.endsWith('/frontend/context/me')) data = { currentRole: 'tienda', tienda: 'T001' };
            else if (path.endsWith('/frontend/capturas/me') || /\/capturas\/[^/]+\/eventos\/me$/.test(path)) status = 201;
            else if (path.endsWith('/cfdi/ocr-preview')) {
                ocrCalls += 1;
                assert.ok(request.postData().includes(`\r\n${documentType}\r\n`), 'OCR keeps the selected document type');
                data = {
                    extracted_total: '100.00', extracted_date: '2026-08-07',
                    suggested_cfdi_uuid: documentType === 'factura' ? (ocrCalls === 1 ? scenario.firstUuid : uuid) : null,
                    verification_token: `test-${ocrCalls}`, checksum_sha256: 'test',
                };
            } else if (/\/cfdi\/uuid\/[^/]+\/availability$/.test(path)) data = { is_available: true };
            else if (path.endsWith('/frontend/solicitudes/me') && request.method() === 'POST') {
                const body = request.postDataJSON();
                creations.push(body);
                const expense = body.gastos[0];
                const id = randomUUID();
                data = {
                    backendId: randomUUID(), id: 'T001-PRUEBA', folio: 'T001-PRUEBA', tienda: 'T001', status: 'Borrador',
                    gastos: [{ backendId: id, id, tipo: expense.categoria, monto: 100, folio: uuid, facturas: 1 }],
                };
                status = 201;
            } else if (/\/expenses\/[^/]+\/attachments$/.test(path)) status = 201;
            else if (path.endsWith('/frontend/bandeja/me') || path.endsWith('/frontend/historico/me')) data = [];
            else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
            await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
        });
        const page = await context.newPage();
        page.on('pageerror', (error) => failures.push(error.message));
        page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
        await page.goto(`${baseURL}/gasto/nuevo`);
        await page.getByRole('heading', { name: 'Añadir Gasto', exact: true }).waitFor();
        await page.getByPlaceholder('DD/MM/AAAA').fill('07/08/2026');
        await page.getByPlaceholder('Ej. 123.45').fill('100');
        const fileIndex = ['factura', 'vale', 'recibo'].indexOf(documentType);
        if (documentType !== 'factura') {
            await page.getByRole('radio', { name: documentType === 'vale' ? 'Cargar Vale' : 'Cargar Recibo' }).check();
        }
        await page.locator('input[type=file]').nth(fileIndex).setInputFiles({
            name: 'scan.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\ncontent\n%%EOF'),
        });
        const validate = page.getByRole('button', { name: 'Validar Gasto', exact: true });
        const folio = page.getByPlaceholder('Ej. 12345678-ABCD-1234-ABCD-1234567890AB');
        async function validateExpense() {
            await validate.click();
            await page.waitForFunction(() => [...document.querySelectorAll('button')]
                .find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
            assert.deepEqual(dialogs, [], 'validation alerts remain unchanged');
        }
        await validateExpense();
        assert.equal(ocrCalls, 1);
        if (documentType === 'factura' && scenario.firstUuid !== uuid) {
            assert.equal(await folio.inputValue(), '');
            assert.ok(await page.getByText(/Folio sugerido: No detectado/).count(), 'missing UUID keeps the existing manual-entry message');
        }
        if (scenario.manual) {
            await folio.fill(uuid);
            await page.getByRole('button', { name: 'Confirmar', exact: true }).click();
            await page.getByRole('button', { name: 'Añadir', exact: true }).click();
            await page.waitForURL('**/solicitud/nueva');
            assert.equal(creations.length, 1);
            assert.equal(creations[0].gastos[0].cfdiUuid, uuid, 'manual UUID is saved without rerunning OCR');
            assert.equal(dialogs.at(-1), '¡Gasto guardado exitosamente en la solicitud!');
        } else {
            await validateExpense();
            assert.equal(ocrCalls, scenario.calls, scenario.name);
            if (documentType === 'factura') {
                assert.equal(await folio.inputValue(), uuid, 'a fresh OCR response fills the fiscal UUID');
                await validateExpense();
            }
        }
        assert.equal(ocrCalls, scenario.calls, `${scenario.name} must not make redundant OCR calls`);
        if (!scenario.manual) {
            await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
            await page.waitForURL('**/solicitud/nueva');
        }
        assert.deepEqual(failures, []);
        await context.close();
    }
    console.log('Browser checks passed: retry missing/empty/invalid UUID, reuse complete invoice, manual UUID save, vale and recibo reuse.');
} finally {
    await browser.close();
}
