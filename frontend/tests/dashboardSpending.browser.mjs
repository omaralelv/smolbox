import assert from 'node:assert/strict';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const years = [2024, 2025, 2026];
const stores = [{ id: 'a', code: 'A016', name: 'Centro' }, { id: 'b', code: 'FE003', name: 'Norte' }];
const data = {
    years, stores,
    rows: [
        { storeId: 'a', storeCode: 'A016', storeName: 'Centro',
            values: { 2024: 10, 2025: 120, 2026: 280 }, normalValues: { 2024: 10, 2025: 100, 2026: 250 },
            extemporaneousValues: { 2024: 0, 2025: 20, 2026: 30 } },
        { storeId: 'b', storeCode: 'FE003', storeName: 'Norte',
            values: { 2024: 10, 2025: 50, 2026: 90 }, normalValues: { 2024: 10, 2025: 50, 2026: 80 },
            extemporaneousValues: { 2024: 0, 2025: 0, 2026: 10 } },
    ],
};

try {
    for (const legacyBackend of [false, true]) {
        const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
        const errors = [];
        let spendingRequests = 0;
        await context.addInitScript(() => {
            localStorage.setItem('smolboxApiToken', 'test-token');
            localStorage.setItem('smolboxFrontendRole', 'tesoreria');
        });
        await context.route('**/api/v1/**', async (route) => {
            const path = new URL(route.request().url()).pathname;
            let response;
            if (path.endsWith('/health')) response = { version: 'test' };
            else if (path.endsWith('/frontend/context/me')) response = { currentRole: 'tesoreria', stores: [], usuario: { nombre: 'Tesoreria' } };
            else if (path.endsWith('/frontend/tesoreria/dashboard/me')) {
                spendingRequests += 1;
                response = legacyBackend ? { ...data, rows: data.rows.map(({ normalValues: _normal, extemporaneousValues: _ext, ...row }) => row) } : data;
            } else { errors.push(`Unexpected API: ${path}`); response = {}; }
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
        });
        const page = await context.newPage();
        page.setDefaultTimeout(10_000);
        page.on('pageerror', (error) => errors.push(error.message));
        await page.goto(`${baseURL}/dashboard`);
        await page.getByRole('heading', { name: 'An\u00e1lisis de Presupuestos' }).waitFor();
        const source = page.getByLabel('Tipo de solicitud:');
        assert.equal(await source.isDisabled(), legacyBackend);
        assert.equal(await source.inputValue(), 'all');
        const currentKpi = page.locator('div').filter({ has: page.getByText('Acumulado 2026', { exact: true }) }).filter({ has: page.getByText('$370.00', { exact: true }) });
        assert.ok(await currentKpi.count() > 0);
        const initialRequests = spendingRequests;
        if (!legacyBackend) {
            async function verify(store, type, current, previous, tableValue) {
                await page.getByLabel('Tienda:').selectOption(store);
                await source.selectOption(type);
                const kpi = page.getByText('Acumulado 2026', { exact: true }).locator('..');
                assert.match(await kpi.innerText(), new RegExp(`\\$${current}\\.00`));
                const previousKpi = page.getByText('Acumulado 2025', { exact: true }).locator('..');
                assert.match(await previousKpi.innerText(), new RegExp(`\\$${previous}\\.00`));
                assert.match(await page.locator('tbody').innerText(), new RegExp(`\\$${tableValue}\\.00`));
                const chart = page.locator('section').filter({ has: page.getByText('2026', { exact: true }) }).filter({ hasNot: page.locator('table') });
                assert.match(await chart.innerText(), new RegExp(`\\$${current}(?![0-9])`));
                assert.equal(spendingRequests, initialRequests);
            }
            await verify('all', 'normal', 330, 150, 250);
            await verify('all', 'extemporaneous', 40, 20, 30);
            await verify('a', 'extemporaneous', 30, 20, 30);
            await verify('b', 'extemporaneous', 10, 0, 10);
            assert.match(await page.locator('tbody').innerText(), /FE003/);
            assert.doesNotMatch(await page.locator('tbody').innerText(), /A016/);
            await verify('b', 'normal', 80, 50, 80);
            await verify('all', 'all', 370, 170, 280);
            await page.screenshot({ path: '/tmp/smolbox-dashboard-filter-desktop.png', fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await verify('a', 'extemporaneous', 30, 20, 30);
            await page.screenshot({ path: '/tmp/smolbox-dashboard-filter-mobile.png', fullPage: true });
            for (const control of [source, page.getByLabel('Tienda:')]) {
                const box = await control.boundingBox();
                assert.ok(box.x >= 0 && box.x + box.width <= 390, JSON.stringify(box));
            }
        }
        assert.deepEqual(errors, []);
        await context.close();
    }
    process.stdout.write('Dashboard source/store filters, KPI, chart, totals, legacy compatibility and mobile: OK\n');
} finally {
    await browser.close();
}
