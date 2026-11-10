import assert from 'node:assert/strict';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });

async function scenario(role, rollover = false) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const failures = [];
    let trayReads = 0;
    let writes = 0;
    let nextDay = false;
    const snapshot = () => rollover && !nextDay ? '2026-10-28T05:59:00Z' : '2026-10-28T18:00:00Z';
    const request = (id, fields) => ({
        id: `T001-${id}`, backendId: id, folio: `T001-${id}`, tienda: 'T001',
        fecha: '28/10/2026', status: 'Enviada', backendStatus: 'submitted', montoTotal: 100,
        firstSubmittedAt: '2026-10-23T18:00:00Z', ageStoppedAt: null,
        ageCalculatedAt: snapshot(), elapsedDays: rollover && !nextDay ? 4 : 5,
        availableActions: [], gastos: [], ...fields,
    });
    const tray = () => [
        request('five-days', { accountingQueueStatus: 'taken' }),
        request('today', { firstSubmittedAt: snapshot(), elapsedDays: 0, accountingQueueStatus: 'taken_other' }),
        request('unknown', { firstSubmittedAt: null, elapsedDays: null, tienda: 'T002' }),
    ];
    const history = () => [
        request('paid', { backendStatus: 'paid', status: 'Pagada', ageStoppedAt: '2026-10-28T18:00:00Z' }),
        request('closed', { backendStatus: 'closed', status: 'Pagada', ageStoppedAt: '2026-10-28T18:00:00Z' }),
        request('rejected', { backendStatus: 'rejected', status: 'Rechazada', ageStoppedAt: '2026-10-25T18:00:00Z', elapsedDays: 2 }),
    ];
    await context.addInitScript((currentRole) => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', currentRole);
    }, role);
    await context.route('**/api/v1/**', async (route) => {
        const req = route.request();
        const path = new URL(req.url()).pathname;
        let data = {};
        let status = 200;
        if (req.method() !== 'GET') writes += 1;
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: role, tienda: 'T001' };
        else if (path.endsWith('/frontend/bandeja/me')) { trayReads += 1; data = tray(); }
        else if (path.endsWith('/frontend/historico/me')) data = history();
        else { failures.push(`Unexpected API ${req.method()} ${path}`); status = 404; }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));
    return {
        context, page, failures, writes: () => writes, reads: () => trayReads,
        advanceDay: () => { nextDay = true; },
    };
}

async function checkCount(page, id, expected) {
    const cell = page.locator(`[data-request-age="${id}"]`);
    await cell.waitFor();
    assert.equal((await cell.textContent()).trim(), expected);
    return cell;
}

try {
    for (const role of ['admin', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'tienda']) {
        const test = await scenario(role);
        await test.page.goto(`${baseURL}/bandeja`);
        await test.page.waitForLoadState('networkidle');
        await checkCount(test.page, 'five-days', '5');
        await checkCount(test.page, 'today', '0');
        await checkCount(test.page, 'unknown', 'Sin fecha');
        if (role === 'contabilidad') {
            await test.page.getByText('Propio', { exact: true }).waitFor();
            await test.page.getByText('Ajeno', { exact: true }).waitFor();
        }
        if (role === 'admin') {
            for (const width of [1366, 390]) {
                await test.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
                const cell = await checkCount(test.page, 'five-days', '5');
                await cell.scrollIntoViewIfNeeded();
                const bounds = await cell.boundingBox();
                assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= width);
                assert.equal(await cell.evaluate((element) => element.scrollWidth > element.clientWidth), false);
                const table = test.page.locator('[data-request-age-table]');
                assert.ok((await table.boundingBox()).width <= width, 'table scroll stays inside the viewport');
                await test.page.screenshot({ path: `/tmp/smolbox-request-age-${width}.png`, fullPage: true });
            }
            await test.page.setViewportSize({ width: 1366, height: 900 });
            await test.page.locator('select').selectOption('T001');
            await checkCount(test.page, 'five-days', '5');
            assert.equal(await test.page.locator('[data-request-age="unknown"]').count(), 0);
        }
        await test.page.goto(`${baseURL}/historico`);
        await test.page.waitForLoadState('networkidle');
        await checkCount(test.page, 'paid', '5');
        const closed = await checkCount(test.page, 'closed', '5');
        assert.ok((await closed.getAttribute('title')).includes('Contador detenido'));
        await checkCount(test.page, 'rejected', '2');
        assert.equal(test.writes(), 0, 'displaying ages does not write or take requests');
        assert.deepEqual(test.failures, []);
        await test.context.close();
    }

    const daily = await scenario('admin', true);
    await daily.page.clock.install({ time: new Date('2026-10-28T05:59:00Z') });
    await daily.page.clock.pauseAt(new Date('2026-10-28T05:59:10Z'));
    await daily.page.goto(`${baseURL}/bandeja`);
    await daily.page.waitForLoadState('networkidle');
    await checkCount(daily.page, 'five-days', '4');
    const before = daily.reads();
    await daily.page.clock.runFor(30_000);
    assert.equal(daily.reads(), before, 'no request is made on every timer tick or per row');
    daily.advanceDay();
    await daily.page.clock.runFor(30_001);
    await daily.page.waitForLoadState('networkidle');
    await checkCount(daily.page, 'five-days', '5');
    assert.equal(daily.reads(), before + 1, 'one list refresh covers all requests at midnight');
    await daily.page.goto(`${baseURL}/historico`);
    await daily.page.waitForLoadState('networkidle');
    await daily.page.clock.fastForward(2 * 86_400_000);
    await checkCount(daily.page, 'paid', '5');
    assert.equal(daily.writes(), 0);
    assert.deepEqual(daily.failures, []);
    await daily.context.close();
    console.log('Browser checks passed: individual request ages, six roles, zero and missing dates, filters, own/other classification, paid/rejected history, Mexico midnight refresh, no writes and desktop/mobile layout.');
} finally {
    await browser.close();
}
