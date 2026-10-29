const EXPENSE_ISSUE_CODES = new Set([
    'missing_authorization',
    'missing_cfdi_xml',
    'invalid_cfdi',
]);
const EXPENSE_ID_FIELDS = {
    missing_authorization: 'missing_authorization_expense_ids',
    missing_cfdi_xml: 'missing_cfdi_expense_ids',
    invalid_cfdi: 'invalid_cfdi_expense_ids',
};

function formatMoney(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return String(value);
    return new Intl.NumberFormat('es-MX', {
        style: 'currency',
        currency: 'MXN',
    }).format(amount);
}

function formatExpenses(expenseIds, expenses) {
    const expensesById = new Map(
        expenses.map((expense) => [
            String(expense.backendId || expense.backend_id || expense.id).toLowerCase(),
            expense,
        ])
    );

    return expenseIds.map((expenseId) => {
        const expense = expensesById.get(String(expenseId).toLowerCase());
        if (!expense) return `gasto ${expenseId}`;

        const label = expense.nombre || expense.tipo || expense.type || 'Gasto';
        const amount = expense.monto === null || expense.monto === undefined
            ? ''
            : `, ${formatMoney(expense.monto)}`;
        return `${label}${amount} (ID ${expenseId})`;
    }).join('; ');
}

export function accountingReadinessBlockers(summary, expenses = []) {
    if (summary?.ready_for_accounting_approval) return [];

    const blockers = [];
    const add = (message) => {
        if (message && !blockers.includes(message)) blockers.push(message);
    };

    if (summary?.expense_count === 0) {
        add('La solicitud no tiene gastos activos por pagar.');
    }

    if (summary?.reported_total === null || summary?.reported_total === undefined) {
        add('Falta registrar el total reportado por la tienda.');
    } else if (
        summary.difference !== null
        && summary.difference !== undefined
        && Number(summary.difference) !== 0
    ) {
        add(
            `El total reportado (${formatMoney(summary.reported_total)}) no coincide `
            + `con la suma de gastos (${formatMoney(summary.calculated_total)}). `
            + `Diferencia: ${formatMoney(summary.difference)}.`
        );
    }

    for (const code of EXPENSE_ISSUE_CODES) {
        const ids = summary?.[EXPENSE_ID_FIELDS[code]] || [];
        if (!ids.length) continue;

        const detail = formatExpenses(ids, expenses);
        if (code === 'missing_authorization') {
            add(`Falta completar la autorización de: ${detail}.`);
        } else if (code === 'missing_cfdi_xml') {
            add(`Falta evidencia fiscal válida para: ${detail}.`);
        } else {
            add(`Hay un CFDI inválido que debe corregirse para: ${detail}.`);
        }
    }

    if (summary?.duplicate_cfdi_uuids?.length) {
        add(`Hay UUID de CFDI duplicados: ${summary.duplicate_cfdi_uuids.join(', ')}.`);
    }

    for (const issue of summary?.issues || []) {
        if (issue.code === 'expense_outside_period' && issue.severity !== 'error') continue;
        if (issue.code === 'missing_receipts') continue;

        switch (issue.code) {
            case 'no_payable_expenses':
                add('La solicitud no tiene gastos activos por pagar.');
                break;
            case 'missing_reported_total':
                add('Falta registrar el total reportado por la tienda.');
                break;
            case 'reported_total_mismatch':
                break;
            case 'missing_authorization':
            case 'missing_cfdi_xml':
            case 'invalid_cfdi':
                break;
            case 'expense_outside_period':
                add('Hay gastos fuera del periodo de reembolso que deben corregirse.');
                break;
            case 'reimbursement_period_unavailable':
                add('No se pudo validar el periodo de reembolso; contacta a soporte.');
                break;
            case 'reimbursement_period_incomplete':
                add('Completa las fechas del periodo de reembolso antes de continuar.');
                break;
            case 'duplicate_cfdi_uuid':
                break;
            default:
                if (issue.severity !== 'warning') {
                    add(issue.message || `La validación "${issue.code}" requiere atención.`);
                }
        }
    }

    if (!blockers.length) {
        add('La API indica que la solicitud no está lista, pero no especificó el motivo.');
    }

    return blockers;
}
