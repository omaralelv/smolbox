import assert from 'node:assert/strict';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const years = [2024, 2025, 2026];
const stores = [{ id: 'a', code: 'A016', name: 'Centro' }, { id: 'b', code: 'FE003', name: 'Norte' },
    { id: 'c', code: 'A017', name: 'Solo normal' }, { id: 'd', code: 'FE004', name: 'Solo archivo' },
    { id: 'z', code: 'Z000', name: 'Acumulado cero' }, { id: 'x', code: 'X000', name: 'Archivo cero' },
    { id: 'e', code: 'EMPTY', name: 'Sin registros' }];
const zeroValues = { 2024: 0, 2025: 0, 2026: 0 };
const data = {
    years, stores,
    rows: [
        { storeId: 'a', storeCode: 'A016', storeName: 'Centro',
            hasNormalData: true, hasExtemporaneousData: true,
            values: { 2024: 10, 2025: 120, 2026: 280 }, normalValues: { 2024: 10, 2025: 100, 2026: 250 },
            extemporaneousValues: { 2024: 0, 2025: 20, 2026: 30 } },
        { storeId: 'b', storeCode: 'FE003', storeName: 'Norte',
            hasNormalData: true, hasExtemporaneousData: true,
            values: { 2024: 10, 2025: 50, 2026: 90 }, normalValues: { 2024: 10, 2025: 50, 2026: 80 },
            extemporaneousValues: { 2024: 0, 2025: 0, 2026: 10 } },
        { storeId: 'c', storeCode: 'A017', storeName: 'Solo normal',
            hasNormalData: true, hasExtemporaneousData: false,
            values: { 2024: 0, 2025: 0, 2026: 100 }, normalValues: { 2024: 0, 2025: 0, 2026: 100 }, extemporaneousValues: zeroValues },
        { storeId: 'd', storeCode: 'FE004', storeName: 'Solo archivo',
            hasNormalData: false, hasExtemporaneousData: true,
            values: { 2024: 0, 2025: 10, 2026: 60 }, normalValues: zeroValues, extemporaneousValues: { 2024: 0, 2025: 10, 2026: 60 } },
        ...stores.slice(4).map((store) => ({
            storeId: store.id, storeCode: store.code, storeName: store.name,
            hasNormalData: store.id === 'z', hasExtemporaneousData: store.id === 'x',
            values: zeroValues, normalValues: zeroValues, extemporaneousValues: zeroValues,
        })),
    ],
};

try {
    for (const version of ['current', 'without-presence', 'without-breakdown']) {
        const legacyBackend = version !== 'current';
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
                response = structuredClone(data);
                if (legacyBackend) for (const row of response.rows) {
                    delete row.hasNormalData;
                    delete row.hasExtemporaneousData;
                    if (version === 'without-breakdown') {
                        delete row.normalValues;
                        delete row.extemporaneousValues;
                    }
                }
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
        const currentKpi = page.locator('div').filter({ has: page.getByText('Acumulado 2026', { exact: true }) }).filter({ has: page.getByText('$530.00', { exact: true }) });
        assert.ok(await currentKpi.count() > 0);
        const initialRequests = spendingRequests;
        async function visibleCodes(expected) {
            assert.deepEqual((await page.locator('tbody td strong').allTextContents()).sort(), expected.toSorted());
        }
        await visibleCodes(legacyBackend ? stores.map((store) => store.code) : ['A016', 'FE003', 'A017', 'FE004', 'Z000', 'X000']);
        if (!legacyBackend) {
            async function verify(store, type, current, previous, tableValue) {
                await page.getByLabel('Tienda:').selectOption(store);
                await source.selectOption(type);
                const kpi = page.getByText('Acumulado 2026', { exact: true }).locator('..');
                assert.match(await kpi.innerText(), new RegExp(`\\$${current}\\.00`));
                const previousKpi = page.getByText('Acumulado 2025', { exact: true }).locator('..');
                assert.match(await previousKpi.innerText(), new RegExp(`\\$${previous}\\.00`));
                if (tableValue === null) {
                    await page.getByText('No hay informaci\u00f3n para mostrar.', { exact: true }).waitFor();
                    await visibleCodes([]);
                } else {
                    assert.match(await page.locator('tbody').innerText(), new RegExp(`\\$${tableValue}\\.00`));
                }
                const chart = page.locator('section').filter({ has: page.getByText('2026', { exact: true }) }).filter({ hasNot: page.locator('table') });
                const currentBar = chart.getByText('2026', { exact: true }).locator('../..');
                assert.match(await currentBar.innerText(), new RegExp(`\\$${current}(?![0-9])`));
                const variance = previous ? `${current >= previous ? '+' : ''}${((current - previous) / previous * 100).toFixed(1)}%` : 'N/A';
                assert.ok((await page.getByText('% Variaci\u00f3n anual', { exact: true }).locator('..').innerText()).includes(variance));
                assert.equal(spendingRequests, initialRequests);
            }
            await verify('all', 'normal', 430, 150, 250);
            await visibleCodes(['A016', 'FE003', 'A017', 'Z000']);
            await verify('all', 'extemporaneous', 100, 30, 30);
            await visibleCodes(['A016', 'FE003', 'FE004', 'X000']);
            await verify('a', 'extemporaneous', 30, 20, 30);
            await verify('b', 'extemporaneous', 10, 0, 10);
            assert.match(await page.locator('tbody').innerText(), /FE003/);
            assert.doesNotMatch(await page.locator('tbody').innerText(), /A016/);
            await verify('b', 'normal', 80, 50, 80);
            await verify('c', 'extemporaneous', 0, 0, null);
            await verify('d', 'normal', 0, 0, null);
            await verify('d', 'all', 60, 10, 60);
            await verify('z', 'normal', 0, 0, 0);
            await visibleCodes(['Z000']);
            await verify('z', 'extemporaneous', 0, 0, null);
            await verify('x', 'extemporaneous', 0, 0, 0);
            await visibleCodes(['X000']);
            await verify('x', 'normal', 0, 0, null);
            await verify('e', 'all', 0, 0, null);
            await verify('all', 'all', 530, 180, 280);
            await visibleCodes(['A016', 'FE003', 'A017', 'FE004', 'Z000', 'X000']);
            await verify('all', 'extemporaneous', 100, 30, 30);
            await page.screenshot({ path: '/tmp/smolbox-dashboard-filter-desktop.png', fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await verify('a', 'extemporaneous', 30, 20, 30);
            await page.screenshot({ path: '/tmp/smolbox-dashboard-filter-mobile.png', fullPage: true });
            for (const control of [source, page.getByLabel('Tienda:')]) {
                const box = await control.boundingBox();
                assert.ok(box.x >= 0 && box.x + box.width <= 390, JSON.stringify(box));
            }
        } else {
            await page.getByLabel('Tienda:').selectOption('e');
            await visibleCodes(['EMPTY']);
            assert.ok((await page.locator('tbody').innerText()).includes('$0.00'));
        }
        assert.deepEqual(errors, []);
        await context.close();
    }
    process.stdout.write('Dashboard eligible-store rows, zero records, empty states, source/store filters, KPI, chart, legacy compatibility and mobile: OK\n');
} finally {
    await browser.close();
}
