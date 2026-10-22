// Dates and fiscal UUIDs must use the same normalization as document validation.
export function requiresExpenseConfirmation({
    documentType, amount, date, fiscalUuid, documentAmount, documentDate, documentFiscalUuid,
}) {
    const enteredAmount = amountForComparison(amount);
    const detectedAmount = amountForComparison(documentAmount);
    if (enteredAmount === null || detectedAmount === null || enteredAmount !== detectedAmount) return true;
    if (!date || !documentDate || date !== documentDate) return true;
    if (documentType === 'vale' || documentType === 'recibo') return false;
    if (documentType !== 'factura') return true;
    return !fiscalUuid || !documentFiscalUuid || fiscalUuid !== documentFiscalUuid;
}

function amountForComparison(value) {
    if (value === null || value === undefined || String(value).trim() === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : null;
}
