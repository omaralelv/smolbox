import assert from 'node:assert/strict';
import process from 'node:process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseURL = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const requestId = '11111111-1111-4111-8111-111111111111';
const expenseId = '22222222-2222-4222-8222-222222222222';

async function scenario(role, initialStatus, action, { failOnce = false } = {}) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const failures = [];
    const transitions = [];
    const clicks = [];
    const dialogs = [];
    let stage = initialStatus;
    let detailReads = 0;
    const targets = {
        approve_authorization: 'authorized',
        start_authorization_review: 'authorization_review',
        start_accounting_review: 'under_accounting_review',
        start_accounting_manager_review: 'accounting_manager_review',
        start_treasury_review: 'treasury_review',
    };
    const payload = () => ({
        backendId: requestId, id: 'T001-NEUTRAL', folio: 'T001-NEUTRAL', tienda: 'T001',
        fecha: '22/10/2026', backendStatus: stage, status: 'Enviada',
        accountingQueueStatus: 'single', totalAmount: 100,
        availableActions: stage === initialStatus ? [action] : [],
        authorizationPendingCount: 0, readyForAuthorizationApproval: true,
        gastos: [{
            backendId: expenseId, id: expenseId, tipo: 'Agua', categoria: 'Agua', monto: 100,
            fecha: '22/10/2026', folio: 'N/A', requiresAuthorization: true,
            backendStatus: 'approved', autorizacion: 'autorizado',
        }],
    });

    await context.addInitScript((currentRole) => {
        localStorage.setItem('smolboxApiToken', 'test-token');
        localStorage.setItem('smolboxFrontendRole', currentRole);
    }, role);
    await context.route('**/api/v1/**', async (route) => {
        const req = route.request();
        const path = new URL(req.url()).pathname;
        let data = {};
        let status = 200;
        if (path.endsWith('/health')) data = { version: 'test' };
        else if (path.endsWith('/frontend/context/me')) data = { currentRole: role, tienda: 'T001' };
        else if (path.endsWith('/frontend/bandeja/me')) data = [payload()];
        else if (path.endsWith(`/solicitudes/${requestId}/me`) && req.method() === 'GET') {
            detailReads += 1;
            data = payload();
        } else if (path.endsWith(`/solicitudes/${requestId}/clicks/me`)) {
            clicks.push(req.postDataJSON());
            status = 201;
        } else if (path.endsWith(`/reimbursement-requests/${requestId}/audit-events`)) data = [];
        else if (path.endsWith(`/reimbursement-requests/${requestId}/transition/me`)) {
            const body = req.postDataJSON();
            transitions.push(body);
            if (failOnce && transitions.length === 1) {
                status = 409;
                data = { detail: { message: 'La solicitud cambio de etapa.' } };
            } else {
                assert.equal(body.action_key, action);
                assert.equal(body.target_status, targets[action]);
                stage = targets[action];
                data = { status: stage };
            }
        } else {
            failures.push(`Unexpected API ${req.method()} ${path}`);
            status = 404;
        }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));
    page.on('dialog', async (dialog) => { dialogs.push(dialog.message()); await dialog.accept(); });
    return {
        page, context, failures, transitions, clicks, dialogs,
        stage: () => stage, reads: () => detailReads,
    };
}

async function openFromTray(test) {
    await test.page.goto(`${baseURL}/bandeja`);
    await test.page.getByText('T001-NEUTRAL', { exact: true }).waitFor();
    await test.page.getByRole('button', { name: 'Abrir', exact: true }).click();
    await test.page.waitForURL(`${baseURL}/acumulado`);
    await test.page.waitForLoadState('networkidle');
    assert.ok(test.reads() > 0, 'request details were refreshed from the backend');
}

try {
    for (const [stage, action] of [
        ['submitted', 'start_accounting_review'],
        ['authorized', 'start_accounting_review'],
        ['submitted', 'start_authorization_review'],
        ['accounting_reviewed', 'start_accounting_manager_review'],
        ['accounting_manager_approved', 'start_treasury_review'],
    ]) {
        const test = await scenario('admin', stage, action);
        await openFromTray(test);
        assert.deepEqual(test.transitions, [], 'admin opening is read-only for workflow');
        assert.equal(test.stage(), stage);

        await test.page.getByText('Ver detalle', { exact: true }).click();
        await test.page.waitForURL(`${baseURL}/detalle`);
        await test.page.waitForLoadState('networkidle');
        assert.deepEqual(test.transitions, [], 'viewing expenses does not transition');
        await test.page.goBack();
        await test.page.waitForLoadState('networkidle');
        await test.page.reload();
        await test.page.waitForLoadState('networkidle');
        assert.deepEqual(test.transitions, [], 'return and reload do not transition');

        const button = test.page.getByRole('button', { name: 'Iniciar revisi\u00f3n', exact: true });
        await button.waitFor();
        if (stage === 'submitted' && action === 'start_accounting_review') {
            for (const width of [1366, 390]) {
                await test.page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
                const bounds = await button.boundingBox();
                assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= width);
                assert.equal(await button.evaluate((element) => element.scrollWidth > element.clientWidth), false);
                await test.page.screenshot({ path: `/tmp/smolbox-admin-review-${width}.png`, fullPage: true });
            }
            await test.page.setViewportSize({ width: 1366, height: 900 });
        }
        await button.click();
        await button.waitFor({ state: 'detached' });
        assert.equal(test.transitions.length, 1, 'exactly one explicitly requested stage change');
        assert.notEqual(test.stage(), stage);
        assert.deepEqual(test.failures, []);
        assert.ok(test.clicks.length > 0, 'existing click audit remains enabled');
        await test.context.close();
    }

    const failed = await scenario('admin', 'submitted', 'start_accounting_review', { failOnce: true });
    await openFromTray(failed);
    const retryButton = failed.page.getByRole('button', { name: 'Iniciar revisi\u00f3n', exact: true });
    await retryButton.click();
    await failed.page.waitForFunction(() => [...document.querySelectorAll('button')]
        .some((button) => button.textContent === 'Iniciar revisi\u00f3n' && !button.disabled));
    assert.equal(failed.stage(), 'submitted', 'a rejected action does not change the stage locally');
    assert.equal(failed.dialogs.length, 1);
    await retryButton.click();
    await retryButton.waitFor({ state: 'detached' });
    assert.equal(failed.transitions.length, 2);
    assert.deepEqual(failed.failures, []);
    await failed.context.close();

    const accountant = await scenario('contabilidad', 'submitted', 'start_accounting_review');
    await openFromTray(accountant);
    assert.equal(accountant.transitions.length, 1, 'accountant auto-review is unchanged');
    assert.equal(accountant.stage(), 'under_accounting_review');
    assert.equal(await accountant.page.getByRole('button', { name: 'Iniciar revisi\u00f3n', exact: true }).count(), 0);
    assert.deepEqual(accountant.failures, []);
    await accountant.context.close();

    for (const role of ['admin', 'supervisor']) {
        const authorization = await scenario(role, 'authorization_review', 'approve_authorization');
        if (role === 'admin') {
            await authorization.page.goto(`${baseURL}/autorizacion`);
            await authorization.page.waitForLoadState('networkidle');
            await authorization.page.reload();
            await authorization.page.waitForLoadState('networkidle');
            assert.deepEqual(authorization.transitions, [], 'admin authorization list never auto-approves');
            assert.equal(authorization.stage(), 'authorization_review');
            assert.deepEqual(authorization.failures, []);
        } else {
            await authorization.page.goto(`${baseURL}/autorizacion`);
            await authorization.page.waitForLoadState('networkidle');
            assert.ok(authorization.transitions.length >= 1, 'supervisor completion stays unchanged');
            assert.equal(authorization.stage(), 'authorized');
            assert.deepEqual(authorization.failures, []);
        }
        await authorization.context.close();
    }
    console.log('Browser checks passed: neutral admin open/detail/return/reload, five manual review paths, retry, accounting auto-review, audit and desktop/mobile layout.');
} finally {
    await browser.close();
}
