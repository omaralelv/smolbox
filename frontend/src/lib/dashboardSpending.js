export function hasSpendingBreakdown(rows, years) {
    return rows.every((row) => row.normalValues && row.extemporaneousValues && years.every((year) => (
        Number.isFinite(row.normalValues?.[year]) && Number.isFinite(row.extemporaneousValues?.[year])
    )));
}

export function filterSpendingRows(rows, storeId = 'all', type = 'all') {
    if (!['all', 'normal', 'extemporaneous'].includes(type)) throw new Error('Tipo de gasto desconocido.');
    const selected = storeId === 'all' ? rows : rows.filter((row) => String(row.storeId) === storeId);
    if (type === 'all') return selected;
    const field = type === 'normal' ? 'normalValues' : 'extemporaneousValues';
    return selected.map((row) => ({ ...row, values: row[field] }));
}
