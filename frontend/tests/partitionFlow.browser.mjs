import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL;
const data = JSON.parse(process.env.PARTITION_TEST_DATA);
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'es-MX', timezoneId: 'America/Mexico_City' });
const page = await context.newPage();
page.setDefaultTimeout(15000);
const issues = [];
const errors = [];
const dialogs = [];
const expectedDialogs = [];
const requests = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
page.on('response', (response) => {
    if (response.url().includes('/api/v1/')) requests.push({ method: response.request().method(), url: new URL(response.url()).pathname, status: response.status() });
});
const rows = () => page.locator('[data-audit-expense-id]');
const modal = () => page.getByRole('heading', { name: 'Particionar Factura', exact: true }).locator('..');

function inspect(id, okay, detail) {
    if (!okay) issues.push({ id, detail });
}

async function api(suffix, options = {}) {
    const token = await page.evaluate(() => localStorage.getItem('smolboxApiToken'));
    const response = await context.request.fetch(`${baseURL}/api/v1/${suffix}`, {
        headers: { Authorization: `Bearer ${token}` }, ...options,
    });
    assert.equal(response.status(), 200, await response.text());
    return response.json();
}

async function openCategory(category = 'Agua') {
    await page.waitForURL('**/acumulado');
    const row = page.getByText(category, { exact: true }).locator('..');
    await row.getByText('Ver detalle', { exact: true }).click();
    await page.waitForURL('**/detalle');
    await rows().first().waitFor();
}

async function fillParts(amounts, rates = ['0', '16']) {
    const panel = modal();
    assert.equal(await panel.locator('input[type=number]').first().inputValue(), '2');
    for (let index = 0; index < amounts.length; index += 1) {
        await panel.locator('select').nth(index * 2).selectOption('Agua');
        await panel.locator('input[type=number]').nth(index + 1).fill(String(amounts[index]));
        await panel.locator('select').nth(index * 2 + 1).selectOption(rates[index]);
    }
}

async function saveParts() {
    const saved = page.waitForResponse((response) => response.url().endsWith('/particiones/me') && response.request().method() === 'POST');
    await modal().getByRole('button', { name: 'Guardar Partición', exact: true }).click();
    assert.equal((await saved).status(), 200);
    await page.getByRole('heading', { name: 'Particionar Factura', exact: true }).waitFor({ state: 'hidden' });
}

async function closeObservations() {
    await page.getByRole('button', { name: 'Observaciones', exact: true }).first().click();
}

async function backToSummary() {
    const latest = await api(`frontend/solicitudes/${data.requestId}/me`);
    const refreshed = page.waitForResponse((response) => response.url().endsWith(`/solicitudes/${data.requestId}/me`)
        && response.request().method() === 'GET');
    await page.getByRole('button', { name: 'Regresar', exact: true }).click();
    await page.waitForURL('**/acumulado');
    await (await refreshed).finished();
    // Wait for the rendered result, not the previous router-state snapshot shown during loading.
    await page.getByText('TOTAL', { exact: true }).locator('..').locator('span').nth(1)
        .filter({ hasText: new RegExp(`^${latest.expenseCount}$`) }).waitFor();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.getByText('Ver detalle', { exact: true }).first().waitFor();
}

try {
    // No API routes are mocked: authentication, partition writes, reads and history use FastAPI.
    await page.goto(`${baseURL}/login`);
    await page.locator('input[type=email]').fill(data.email);
    await page.locator('input[type=password]').fill('secret-password');
    await page.getByRole('button', { name: 'Entrar', exact: true }).click();
    await page.waitForURL('**/bandeja');
    await page.getByText(data.folio, { exact: true }).locator('..').getByRole('button', { name: 'Abrir', exact: true }).click();
    await openCategory();
    assert.equal(await rows().count(), 1);
    await page.getByRole('button', { name: 'Observaciones', exact: true }).first().click();
    await page.getByText('Nota original de tienda', { exact: true }).waitFor();
    inspect('known-accounting-chat-mapping', await page.getByPlaceholder('Nueva observación...').count() === 1,
        'Acumulado -> Detalle drops canAddObservation; the accountant composer is absent.');
    await page.getByPlaceholder('Nueva observación...').fill('Comentario de contabilidad en gasto original');
    await page.getByRole('button', { name: 'Enviar observación', exact: true }).evaluate((button) => { button.click(); button.click(); });
    await page.getByText('Comentario de contabilidad en gasto original', { exact: true }).waitFor();
    await closeObservations();

    await page.getByTitle('Particionar Gasto', { exact: true }).click();
    await fillParts([900, 600]);
    await saveParts();
    assert.equal(await rows().count(), 2);
    assert.equal(await page.locator(`[data-audit-expense-id="${data.parentId}"]`).count(), 0);
    assert.equal(await page.getByTitle('Gasto proveniente de una partición', { exact: true }).count(), 2);
    assert.equal(await page.getByTitle('Gasto proveniente de una partición', { exact: true }).first().isDisabled(), true);
    await page.screenshot({ path: path.join(data.outputDir, 'partition-created.png'), fullPage: true });

    const first = await api(`frontend/solicitudes/${data.requestId}/me`);
    assert.equal(first.expenseCount, 2);
    assert.equal(first.montoTotal, 1500);
    const firstIds = first.gastos.filter((g) => g.esHijoParticion).map((g) => g.backendId);
    await rows().first().getByTitle('Ver Documento', { exact: true }).click();
    await page.locator('pre').filter({ hasText: 'TimbreFiscalDigital' }).waitFor();
    assert.ok(requests.some((r) => r.url.includes('/attachments/') && r.status === 200));
    await page.getByTitle('Cerrar', { exact: true }).click();

    // Lose one response after the real server commits, then retry the exact submission.
    await rows().first().getByRole('button', { name: 'Observaciones', exact: true }).click();
    const editor = page.getByPlaceholder('Nueva observación...');
    await editor.fill('Comentario anterior a editar la partición');
    const attempts = [];
    let retryHandled;
    const handledRetry = new Promise((resolve) => { retryHandled = resolve; });
    const observationRoute = '**/expenses/*/observation/me';
    await context.route(observationRoute, async (route) => {
        attempts.push(route.request().postDataJSON());
        const attempt = attempts.length;
        const response = await route.fetch();
        assert.equal(response.status(), 200);
        await response.body();
        if (attempt === 1) await route.abort('failed');
        else {
            await route.fulfill({ response });
            retryHandled();
        }
    });
    const lostResponseDialog = page.waitForEvent('dialog');
    await page.getByRole('button', { name: 'Enviar observación', exact: true }).click();
    expectedDialogs.push((await lostResponseDialog).message());
    assert.equal(await editor.inputValue(), 'Comentario anterior a editar la partición');
    await page.getByRole('button', { name: 'Enviar observación', exact: true }).click();
    await handledRetry;
    await page.getByText('Comentario anterior a editar la partición', { exact: true }).waitFor();
    await context.unroute(observationRoute);
    assert.equal(attempts.length, 2);
    assert.equal(attempts[0].eventId, attempts[1].eventId);
    await closeObservations();

    await rows().first().getByTitle('Editar Gasto', { exact: true }).click();
    await fillParts([1100, 400], ['8', '0']);
    await saveParts();
    assert.equal(await rows().count(), 2);
    await rows().first().getByRole('button', { name: 'Observaciones', exact: true }).click();
    await page.getByText(/Partición editada sobre/).first().waitFor();
    inspect('child-note-after-replacement', await page.getByText('Comentario anterior a editar la partición', { exact: true }).count() === 1,
        'Editing replaces child IDs; the previous child comment remains in the database but is not displayed.');
    await closeObservations();

    await backToSummary();
    await openCategory();
    assert.equal(await rows().count(), 2);
    const partitionColors = await rows().evaluateAll((elements) => elements.map((el) => el.style.backgroundColor));
    assert.ok(partitionColors.every((color) => color && color === partitionColors[0] && color !== 'rgb(255, 255, 255)'));
    await rows().first().getByTitle('Editar Gasto', { exact: true }).click();
    assert.equal(await modal().locator('input[type=number]').count(), 3, 'only two current parts are loaded into edit');
    assert.deepEqual(await modal().locator('input[type=number]').evaluateAll((inputs) => inputs.slice(1).map((input) => input.value)), ['1100', '400']);
    await modal().getByRole('button', { name: 'Anular partición', exact: true }).click();
    await page.getByRole('button', { name: 'Confirmar', exact: true }).click();
    await page.getByTitle('Particionar Gasto', { exact: true }).waitFor();
    assert.equal(await rows().count(), 1);
    assert.equal(await rows().first().getAttribute('data-audit-expense-id'), data.parentId);
    await rows().first().getByRole('button', { name: 'Observaciones', exact: true }).click();
    await page.getByText('Comentario anterior a editar la partición', { exact: true }).waitFor();
    await page.getByText('Partición anterior 1/2', { exact: true }).waitFor();
    await closeObservations();

    await page.getByTitle('Particionar Gasto', { exact: true }).click();
    assert.equal(await modal().locator('input[type=number]').count(), 3);
    assert.deepEqual(await modal().locator('select').evaluateAll((inputs) => inputs.map((input) => input.value)), ['', '0', '', '0']);
    await fillParts([800, 700]);
    await saveParts();
    assert.equal(await rows().count(), 2);
    const current = await api(`frontend/solicitudes/${data.requestId}/me`);
    assert.equal(current.expenseCount, 2);
    assert.equal(current.montoTotal, 1500);
    assert.equal(current.gastos.filter((g) => firstIds.includes(g.backendId)).length, 0);
    await page.screenshot({ path: path.join(data.outputDir, 'partition-recreated.png'), fullPage: true });

    // Reload without navigating away: route state must not resurrect an earlier snapshot.
    const idsBeforeReload = await rows().evaluateAll((elements) => elements.map((el) => el.dataset.auditExpenseId).sort());
    await page.reload();
    await rows().first().waitFor();
    const idsAfterReload = await rows().evaluateAll((elements) => elements.map((el) => el.dataset.auditExpenseId).sort());
    inspect('detail-reload-stale-partitions', JSON.stringify(idsBeforeReload) === JSON.stringify(idsAfterReload),
        'Reloading Detalle renders the previous router-state partitions instead of fetching the current request.');
    await backToSummary();
    await openCategory();
    assert.deepEqual(await rows().evaluateAll((elements) => elements.map((el) => el.dataset.auditExpenseId).sort()), idsBeforeReload);
    await rows().first().getByRole('button', { name: 'Observaciones', exact: true }).click();
    await page.getByText(/Partición creada sobre/).first().waitFor();
    inspect('known-missing-partition-created-at', !(await page.locator('body').innerText()).includes('Fecha no disponible'),
        'Acumulado also drops createdAt before opening the partition history.');
    assert.equal(await page.getByText('Comentario anterior a editar la partición', { exact: true }).count(), 1);
    assert.equal(await page.getByText('Comentario de contabilidad en gasto original', { exact: true }).count(), 1);
    await page.screenshot({ path: path.join(data.outputDir, 'partition-history.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(data.outputDir, 'partition-mobile.png'), fullPage: true });
    const history = await api(`reimbursement-requests/${data.requestId}/audit-events?observations_only=true&limit=200`);
    assert.ok(history.some((event) => event.action === 'expense_partitioned'));
    assert.ok(history.some((event) => event.action === 'expense_partition_updated'));
    assert.ok(history.some((event) => event.action === 'expense_partition_cancelled'));
    assert.ok(history.some((event) => event.message === 'Comentario anterior a editar la partición'));
    assert.equal(history.filter((event) => event.message === 'Comentario anterior a editar la partición').length, 1);
    assert.equal(history.filter((event) => event.message === 'Comentario de contabilidad en gasto original').length, 1);
    assert.deepEqual(errors, []);
    assert.deepEqual(dialogs.filter((text) => !text.includes('correctamente')), expectedDialogs);
    console.log(JSON.stringify({ checks: 'Real login -> tray -> summary -> detail -> create -> evidence -> comment -> edit -> summary -> cancel -> recreate -> reload -> history', issues, apiRequestCount: requests.length }, null, 2));
    assert.deepEqual(issues, [], 'The complete journey finished, but these regressions remain reproducible');
} catch (error) {
    await page.screenshot({ path: path.join(data.outputDir, 'partition-failure.png'), fullPage: true });
    throw error;
} finally {
    await writeFile(path.join(data.outputDir, 'partition-browser-results.json'), JSON.stringify({ issues, errors, dialogs, requests }, null, 2));
    await context.close();
    await browser.close();
}
