import assert from 'node:assert/strict';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const roles = ['supervisor', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin', 'tienda'];

try {
    for (const role of roles) {
        const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
        const failures = [];
        await context.route('**/api/v1/**', async (route) => {
            const request = route.request();
            const path = new URL(request.url()).pathname;
            let data = {};
            let status = 200;
            if (path.endsWith('/health')) data = { version: 'test' };
            else if (path.endsWith('/auth/login') && request.method() === 'POST') data = { access_token: 'test-token' };
            else if (path.endsWith('/frontend/context/me')) data = { currentRole: role, tienda: 'T001' };
            else if ([
                '/frontend/bandeja/me', '/frontend/historico/me', '/users/', '/stores/', '/authorization-areas/',
            ].some((suffix) => path.endsWith(suffix))) data = [];
            else { failures.push(`Unexpected API ${request.method()} ${path}`); status = 404; }
            await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
        });

        const page = await context.newPage();
        page.on('pageerror', (error) => failures.push(error.message));
        await page.goto(`${baseURL}/login`);
        await page.locator('input[type=email]').fill(`${role}@example.com`);
        await page.locator('input[type=password]').fill('test-password');
        await page.getByRole('button', { name: 'Entrar', exact: true }).click();

        const destination = role === 'supervisor' ? '/autorizacion' : role === 'admin' ? '/usuarios' : '/bandeja';
        await page.waitForURL(`${baseURL}${destination}`);
        await page.getByAltText('Smolbox Logo').waitFor();
        assert.equal(await page.evaluate(() => localStorage.getItem('smolboxFrontendRole')), role);

        if (role === 'supervisor') {
            await page.getByRole('link', { name: 'Autorizaci\u00f3n', exact: true }).waitFor();
            assert.equal(await page.getByRole('link', { name: 'Bandeja', exact: true }).count(), 0);
            assert.deepEqual(await page.locator('a[href]').evaluateAll((links) => links.map((link) => link.getAttribute('href'))), ['/autorizacion']);

            await page.getByAltText('Smolbox Logo').click();
            await page.waitForURL(`${baseURL}/autorizacion`);
            assert.equal(new URL(page.url()).pathname, '/autorizacion', 'logo keeps the authorizer on Authorization');

            await page.goto(`${baseURL}/bandeja`);
            await page.waitForURL(`${baseURL}/autorizacion`);
            await page.reload();
            await page.getByRole('link', { name: 'Autorizaci\u00f3n', exact: true }).waitFor();
            assert.equal(new URL(page.url()).pathname, '/autorizacion', 'reload keeps the role restriction');

            await page.setViewportSize({ width: 390, height: 844 });
            assert.equal(await page.getByRole('link', { name: 'Bandeja', exact: true }).count(), 0);
            await page.getByRole('link', { name: 'Autorizaci\u00f3n', exact: true }).waitFor();
            await page.screenshot({ path: '/tmp/smolbox-authorizer-navigation-mobile.png', fullPage: true });
            await page.setViewportSize({ width: 1366, height: 900 });
            await page.screenshot({ path: '/tmp/smolbox-authorizer-navigation-desktop.png', fullPage: true });
        } else {
            const trayLabel = role === 'tienda' ? 'Monitoreo' : 'Bandeja';
            await page.getByRole('link', { name: trayLabel, exact: true }).waitFor();
            await page.getByAltText('Smolbox Logo').click();
            await page.waitForURL(`${baseURL}/bandeja`);
            await page.goto(`${baseURL}/bandeja`);
            assert.equal(new URL(page.url()).pathname, '/bandeja', `${role} retains access to its tray`);
            await page.getByRole('link', { name: trayLabel, exact: true }).waitFor();
        }

        assert.deepEqual(failures, [], role);
        await page.getByRole('button', { name: 'Cerrar sesi\u00f3n', exact: true }).click();
        await page.waitForURL(`${baseURL}/login`);
        await page.goto(`${baseURL}/bandeja`);
        await page.waitForURL(`${baseURL}/login`);
        assert.equal(await page.evaluate(() => localStorage.getItem('smolboxApiToken')), null, 'logout clears the session');
        assert.deepEqual(failures, [], `${role} logout`);
        await context.close();
    }
    console.log('Browser checks passed: authorizer login, logo, direct route and reload; other six roles and unauthenticated access.');
} finally {
    await browser.close();
}
