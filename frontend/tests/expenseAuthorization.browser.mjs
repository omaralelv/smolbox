import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { randomUUID } from 'node:crypto';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });

try {
    for (const category of ['No Deducibles', 'Pasajes y Taxis']) {
        const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
        const creations = [];
        const dialogs = [];
        const failures = [];
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
                data = { extracted_total: '100.00', extracted_date: '2026-08-07', verification_token: 'test', checksum_sha256: 'test' };
            } else if (path.endsWith('/frontend/solicitudes/me') && request.method() === 'POST') {
                const body = request.postDataJSON();
                creations.push(body);
                const expense = body.gastos[0];
                const id = randomUUID();
                data = { backendId: randomUUID(), id: 'T001-PRUEBA', folio: 'T001-PRUEBA', tienda: 'T001', status: 'Borrador',
                    gastos: [{ backendId: id, id, tipo: expense.categoria, monto: 100, folio: 'N/A', facturas: 1,
                        authorizationArea: expense.authorizationArea, requiresAuthorization: true, cfdiTaxRate: 0 }] };
                status = 201;
            } else if (/\/expenses\/[^/]+\/attachments$/.test(path)) status = 201;
            else if (path.endsWith('/frontend/bandeja/me') || path.endsWith('/frontend/historico/me') || path.endsWith('/audit-events')) data = [];
            else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
            await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
        });
        const page = await context.newPage();
        page.on('pageerror', (error) => failures.push(error.message));
        page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
        await page.goto(`${baseURL}/gasto/nuevo`);
        await page.getByRole('heading', { name: 'Añadir Gasto', exact: true }).waitFor();
        const categories = page.locator('select').first();
        const area = page.locator('select').nth(1);
        assert.equal(await area.isDisabled(), true, 'regular category keeps its automatic area');
        await categories.selectOption(category);
        assert.equal(await area.isEnabled(), true);
        assert.equal(await area.evaluate((element) => element.required), true);
        const missingArea = `Selecciona el área que autoriza para ${category}.`;
        await page.getByRole('button', { name: 'Validar Gasto', exact: true }).click();
        assert.equal(dialogs.at(-1), missingArea);
        await page.getByRole('button', { name: 'Añadir', exact: true }).click();
        assert.equal(dialogs.at(-1), missingArea);
        assert.equal(ocrCalls, 0);
        assert.equal(creations.length, 0);

        await area.selectOption('Sistemas');
        await page.getByPlaceholder('DD/MM/AAAA').fill('07/08/2026');
        await page.getByPlaceholder('Ej. 123.45').fill('100');
        await page.getByRole('radio', { name: 'Cargar Vale' }).check();
        await page.locator('input[type=file]').nth(1).setInputFiles({ name: 'vale.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\ncontent\n%%EOF') });
        if (category === 'No Deducibles') {
            await page.screenshot({ path: '/tmp/smolbox-no-deducibles-desktop.png', fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: '/tmp/smolbox-no-deducibles-mobile.png', fullPage: true });
            await page.setViewportSize({ width: 1366, height: 900 });
        }
        const ocrResponse = page.waitForResponse('**/cfdi/ocr-preview');
        await page.getByRole('button', { name: 'Validar Gasto', exact: true }).click();
        await ocrResponse;
        await page.waitForFunction(() => [...document.querySelectorAll('button')]
            .find((button) => button.textContent.trim() === 'Validar Gasto')?.disabled === false);
        await area.selectOption('');
        await page.getByRole('button', { name: 'Añadir', exact: true }).click();
        assert.equal(dialogs.at(-1), missingArea, 'clearing an area after validation still blocks saving');
        assert.equal(creations.length, 0);
        await area.selectOption('Sistemas');
        await page.getByRole('button', { name: 'Añadir', exact: true }).click();
        const confirmation = page.getByRole('dialog', { name: 'RESUMEN DEL GASTO' });
        await confirmation.waitFor();
        assert.equal(creations.length, 0, 'reviewing the summary does not save an expense');
        await confirmation.getByRole('checkbox').check();
        await confirmation.getByRole('button', { name: 'Confirmar y A\u00f1adir', exact: true }).click();
        await page.waitForURL('**/solicitud/nueva');
        assert.equal(creations.length, 1);
        assert.equal(creations[0].gastos[0].categoria, category);
        assert.equal(creations[0].gastos[0].authorizationArea, 'Sistemas');
        assert.equal(creations[0].gastos[0].requiresAuthorization, true);
        assert.equal(dialogs.at(-1), '¡Gasto guardado exitosamente en la solicitud!');
        assert.deepEqual(failures, []);
        await context.close();
    }
    console.log('Browser checks passed: mandatory area on validation/save, selected-area payload and taxi regression.');
} finally {
    await browser.close();
}
